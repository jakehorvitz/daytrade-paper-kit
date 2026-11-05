"""Optional injected LLM adapter; no provider or network access is supplied."""
import json
import math
import queue
import threading
from pathlib import Path
from .strategy import Signal


def parse_signal(raw):
    try:
        def unique_pairs(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError('duplicate key')
                obj[key] = value
            return obj
        obj = json.loads(raw, object_pairs_hook=unique_pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(obj, dict) or set(obj) != {'action', 'confidence', 'reason'}:
            raise ValueError('schema')
        confidence = obj['confidence']
        if obj['action'] not in ('buy', 'sell', 'hold') or isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1 or not isinstance(obj['reason'], str):
            raise ValueError('schema')
        return Signal(obj['action'], confidence, obj['reason'])
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return Signal('hold', 0, 'invalid response')


class LLMAdapter:
    def __init__(self, provider, log_path='reports/llm_log.jsonl', timeout=10):
        self.provider, self.log_path, self.timeout = provider, Path(log_path), timeout

    def signal(self, bars):
        result = queue.Queue(maxsize=1)
        def log(raw):
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'raw': raw}, default=str) + '\n')
        def call():
            try:
                raw = self.provider(bars)
                log(raw)
                result.put((True, raw))
            except Exception as exc:
                result.put((False, f'provider error: {type(exc).__name__}'))
        threading.Thread(target=call, daemon=True).start()
        try:
            ok, raw = result.get(timeout=self.timeout)
        except queue.Empty:
            ok, raw = False, 'timeout'
        if not ok:
            log(raw)
        return parse_signal(raw) if ok and isinstance(raw, str) else Signal('hold', 0, 'timeout or provider failure')
