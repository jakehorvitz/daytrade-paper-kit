import csv
from datetime import timezone
import pytest
from daytrade.data import load_csv

HEADER = ['timestamp','open','high','low','close','volume']
GOOD = ['2025-01-02T09:30:00-05:00','10','12','9','11','0']

def write(path, rows, header=HEADER):
    with path.open('w', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

@pytest.mark.parametrize('field,value', [('open','no'),('high','NaN'),('low','0'),('close','-1'),('volume','-1'),('volume','inf'),('timestamp','bad'),('timestamp','2025-01-02T09:30:00')])
def test_invalid_field(tmp_path, field, value):
    row = GOOD.copy(); row[HEADER.index(field)] = value
    p = tmp_path/'x.csv'; write(p,[row])
    with pytest.raises(ValueError, match='row 2.*'+field): load_csv(p)

@pytest.mark.parametrize('field,value,rule', [('high','8','high below low'),('open','13','open outside'),('close','8','close outside')])
def test_invalid_ohlc(tmp_path,field,value,rule):
    row=GOOD.copy(); row[HEADER.index(field)]=value
    p=tmp_path/'x.csv'; write(p,[row])
    with pytest.raises(ValueError,match=rule): load_csv(p)

def test_missing_and_normalized_order(tmp_path):
    p=tmp_path/'x.csv'; write(p,[GOOD],HEADER[:-1])
    with pytest.raises(ValueError,match='row 1.*missing'): load_csv(p)
    duplicate=GOOD.copy(); duplicate[0]='2025-01-02T14:30:00Z'
    write(p,[GOOD,duplicate])
    with pytest.raises(ValueError,match='row 3.*duplicate'): load_csv(p)
    earlier=GOOD.copy(); earlier[0]='2025-01-02T14:29:00Z'
    write(p,[GOOD,earlier])
    with pytest.raises(ValueError,match='row 3.*non-monotonic'): load_csv(p)
    write(p,[GOOD]); assert load_csv(p)[0].timestamp.tzinfo == timezone.utc
