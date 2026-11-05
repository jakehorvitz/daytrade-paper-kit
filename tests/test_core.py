import json
import socket
import time
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from daytrade.broker import AlpacaPaperStub, SimulatedBroker, PAPER_URL
from daytrade.data import Bar, load_csv
from daytrade.risk import RiskManager
from daytrade.strategy import sma_signal, Signal
from daytrade.llm import LLMAdapter, parse_signal
from daytrade.backtest import replay, run

SAMPLE = Path(__file__).resolve().parents[1]/'examples/sample.csv'

def test_alpaca_fails_before_network(monkeypatch):
    monkeypatch.setattr(socket, 'socket', lambda *a,**k: pytest.fail('network used'))
    with pytest.raises(ValueError): AlpacaPaperStub('https://api.alpaca.markets')
    assert AlpacaPaperStub().base_url == PAPER_URL
    with pytest.raises(NotImplementedError): AlpacaPaperStub().submit()

def test_pending_gap_and_kill(tmp_path):
    risk=RiskManager(kill_path=tmp_path/'kill.json'); broker=SimulatedBroker(cash=1000)
    assert broker.submit('buy', 10, 10, risk)
    assert not broker.submit('buy', 1, 10, risk)
    broker.fill_pending(20, risk)
    assert broker.position * 20 <= broker.equity(20)*.1 + 1e-8
    assert not risk.allowed('buy', 1, 20, broker.equity(20),broker.position)
    risk.trip('test'); assert not broker.submit('sell', broker.position, 20, risk)
    assert RiskManager(kill_path=tmp_path/'kill.json').killed()
    risk.clear_manually(); assert not risk.killed()

def test_daily_loss_ny_and_unrealized(tmp_path):
    r=RiskManager(kill_path=tmp_path/'kill.json')
    assert r.observe(datetime(2025,1,2,23,tzinfo=timezone.utc),1000)
    assert not r.observe(datetime(2025,1,3,3,tzinfo=timezone.utc),979)
    assert r.killed()
    r.clear_manually(); assert r.observe(datetime(2025,1,3,14,tzinfo=timezone.utc),979)

def test_determinism_and_next_open(tmp_path):
    bars=load_csv(SAMPLE); closes=[x.close for x in bars]
    assert sma_signal(closes)==sma_signal(closes)
    replayed=replay(bars, kill_path=tmp_path/'kill')
    assert replayed['fills']
    for fill in replayed['fills']:
        i=next(i for i,b in enumerate(bars) if b.timestamp.isoformat()==fill['timestamp'])
        assert i > 0 and sma_signal([b.close for b in bars[:i]]).action == fill['action']
        expected=bars[i].open*(1.0005 if fill['action']=='buy' else .9995)
        assert fill['price']==pytest.approx(expected)

def test_holdout_reports_and_fresh_account(tmp_path):
    bars=load_csv(SAMPLE)
    s=run(bars, output_dir=tmp_path/'reports', kill_path=tmp_path/'kill')
    assert s['holdout_bars']==24 and s['costs']=={'slippage_bps':5,'commission':0}
    assert json.loads((tmp_path/'reports/summary.json').read_text())==s
    assert len((tmp_path/'reports/equity_curve.csv').read_text().splitlines())==121
    direct=replay(bars,96,kill_path=tmp_path/'kill')
    assert s['holdout']['baseline_return']==direct['net_total_return']
    with pytest.raises(ValueError,match='insufficient bars'): run(bars[:10],output_dir=tmp_path)

def test_full_trip_does_not_contaminate_holdout_and_existing_kill_is_honored(tmp_path, monkeypatch):
    import daytrade.backtest as bt
    monkeypatch.setattr(bt, 'sma_signal', lambda *args: Signal('buy'))
    start = datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc)
    prices = [100] * 10 + [1] * 70 + [1 + .05 * i for i in range(20)]
    bars = [Bar(start + timedelta(minutes=i), p, p, p, p, 1) for i, p in enumerate(prices)]
    switch = tmp_path/'kill'
    summary = run(bars, output_dir=tmp_path/'reports', kill_path=switch)
    assert RiskManager(kill_path=switch).killed()
    independent = replay(bars, 80, kill_path=tmp_path/'fresh')
    assert independent['net_total_return'] > 0
    assert summary['holdout']['baseline_return'] == pytest.approx(independent['net_total_return'])
    blocked = run(bars, output_dir=tmp_path/'blocked', kill_path=switch)
    assert blocked['holdout']['baseline_return'] == 0
    assert blocked['holdout']['benchmark_return'] == 0

def test_cli_missing_input_disclaimer(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'daytrade.backtest', str(tmp_path/'missing.csv')], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'PAPER ONLY' in result.stdout and 'no profitability claim' in result.stdout

@pytest.mark.parametrize('raw', ['bad','{"action":"buy","confidence":true,"reason":"x"}', '{"action":"buy","confidence":NaN,"reason":"x"}', '{"action":"buy","confidence":2,"reason":"x"}', '{"action":"sell","confidence":1,"reason":1}', '{"action":"buy","confidence":1,"reason":"x","extra":0}'])
def test_invalid_llm_holds(raw): assert parse_signal(raw).action == 'hold'

def test_llm_duplicate_and_large_number_hold():
    assert parse_signal('{"action":"buy","action":"sell","confidence":1,"reason":"x"}').action == 'hold'
    assert parse_signal('{"action":"buy","confidence":' + '9' * 400 + ',"reason":"x"}').action == 'hold'
    assert parse_signal('{"action":"hold","confidence":0,"reason":' + '[' * 1100 + '0' + ']' * 1100 + '}').action == 'hold'

def test_llm_timeout_and_log(tmp_path):
    def slow(_): time.sleep(.4); return '{"action":"buy","confidence":1,"reason":"x"}'
    a=LLMAdapter(slow,tmp_path/'log',timeout=.03)
    t=time.monotonic(); assert a.signal([]).action=='hold'; assert time.monotonic()-t < .2
    assert json.loads((tmp_path/'log').read_text())['raw']=='timeout'
    assert parse_signal('{"action":"buy","confidence":0.9,"reason":"x"}').action=='buy'

def test_llm_summary_comparison_and_risk(tmp_path):
    bars=load_csv(SAMPLE)
    a=LLMAdapter(lambda _: '{"action":"buy","confidence":1,"reason":"x"}',tmp_path/'llm')
    s=run(bars,adapter=a,output_dir=tmp_path/'reports',kill_path=tmp_path/'kill')
    assert s['llm']['beats_baseline'] == (s['llm']['holdout_return'] > s['llm']['baseline_holdout_return'])
    RiskManager(kill_path=tmp_path/'kill').trip('manual')
    assert not replay(bars,96,mode='llm',adapter=a,kill_path=tmp_path/'kill')['fills']
