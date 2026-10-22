import os
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request

app = Flask(__name__)
KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------
# 고정 길이 큐 (원형 배열 기반 Fixed-Size Queue)
# ---------------------------------------------------------------
class FixedSizeQueue:
    def __init__(self, capacity=20):
        self.init(capacity)

    # 1) 초기화
    def init(self, capacity):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("큐 크기는 1 이상이어야 합니다.")
        self.capacity = capacity
        self.data = [None] * capacity
        self.front = 0
        self.count = 0

    @property
    def rear(self):
        if self.count == 0:
            return -1
        return (self.front + self.count - 1) % self.capacity

    def is_full(self):
        return self.count == self.capacity

    def is_empty(self):
        return self.count == 0

    # 2) push
    def push(self, value):
        if self.is_full():
            raise OverflowError(f"큐가 가득 찼습니다(FULL). {value} push 실패")
        idx = (self.front + self.count) % self.capacity
        self.data[idx] = value
        self.count += 1

    # 2) pop
    def pop(self):
        if self.is_empty():
            raise IndexError("큐가 비어 있습니다(EMPTY). pop 실패")
        value = self.data[self.front]
        self.data[self.front] = None
        self.front = (self.front + 1) % self.capacity
        self.count -= 1
        return value

    # 5) Front 데이터 확인
    def peek(self):
        if self.is_empty():
            raise IndexError("큐가 비어 있습니다(EMPTY). Front 데이터 없음")
        return self.data[self.front]

    # 6) 전체 데이터 삭제 (크기는 유지)
    def clear(self):
        self.data = [None] * self.capacity
        self.front = 0
        self.count = 0

    # 10) Front부터 Rear까지
    def items(self):
        return [self.data[(self.front + i) % self.capacity] for i in range(self.count)]

    # 7) 값의 index 검색 (Front 기준 0부터)
    def positions(self, value):
        return [i for i, v in enumerate(self.items()) if v == value]

    # 8) 값의 개수
    def count_of(self, value):
        return len(self.positions(value))

    # 9) 값의 존재 여부
    def contains(self, value):
        return self.count_of(value) > 0

    def snapshot(self):
        return {
            "capacity": self.capacity,
            "size": self.count,
            "frontIndex": self.front if self.count else -1,
            "rearIndex": self.rear,
            "isFull": self.is_full(),
            "isEmpty": self.is_empty(),
            "items": self.items(),   # Front -> Rear 순서
            "array": self.data,      # 실제 내부 배열
        }


queue = FixedSizeQueue(20)
history = []  # 서버 동작 기록 (상태 화면용)


# ---------------------------------------------------------------
# 공통 함수
# ---------------------------------------------------------------
def param(name, default=None):
    body = request.get_json(silent=True) or {}
    if name in body:
        return body[name]
    return request.args.get(name, default)


def parse_value(v):
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def record(action, message, ok=True):
    entry = {
        "time": datetime.now(KST).strftime("%H:%M:%S"),
        "action": action,
        "message": message,
        "ok": ok,
    }
    history.append(entry)
    del history[:-50]
    print(f"[{entry['time']}] {action} -> {message}", flush=True)


def ok(action, message, result=None):
    record(action, message)
    return jsonify({"ok": True, "action": action, "message": message,
                    "result": result, "queue": queue.snapshot()})


def fail(action, message, code=400):
    record(action, message, ok=False)
    return jsonify({"ok": False, "action": action, "error": message,
                    "message": message, "queue": queue.snapshot()}), code


def required_value(action):
    v = param("value")
    if v is None or str(v).strip() == "":
        return None, fail(action, "value 값이 필요합니다.")
    return parse_value(v), None


# ---------------------------------------------------------------
# API
# ---------------------------------------------------------------
@app.route("/init", methods=["GET", "POST"])
def api_init():
    try:
        size = int(param("size", 20))
        queue.init(size)
        return ok("init", f"큐 초기화 완료 (크기 {size})", size)
    except (ValueError, TypeError) as e:
        return fail("init", str(e))


@app.route("/push", methods=["GET", "POST"])
def api_push():
    values = param("values")
    if values is not None:  # 배열 push
        if isinstance(values, str):
            values = [x for x in values.split(",") if x.strip() != ""]
        values = [parse_value(v) for v in values]
        pushed = []
        for v in values:
            try:
                queue.push(v)
                pushed.append(v)
            except OverflowError as e:
                return fail("push", f"{len(pushed)}개 push 후 중단: {e}")
        return ok("push", f"{len(pushed)}개 push 완료: {pushed}", pushed)

    value, err = required_value("push")
    if err:
        return err
    try:
        queue.push(value)
        return ok("push", f"{value} push 완료", value)
    except OverflowError as e:
        return fail("push", str(e))


@app.route("/pop", methods=["GET", "POST"])
def api_pop():
    try:
        v = queue.pop()
        return ok("pop", f"{v} pop 완료", v)
    except IndexError as e:
        return fail("pop", str(e))


@app.route("/size", methods=["GET", "POST"])
def api_size():
    return ok("size", f"현재 데이터 개수: {queue.count} (큐 크기 {queue.capacity})", queue.count)


@app.route("/status", methods=["GET", "POST"])
def api_status():
    full, empty = queue.is_full(), queue.is_empty()
    state = "FULL" if full else ("EMPTY" if empty else "NORMAL (데이터 있음, 여유 공간 있음)")
    return ok("status", f"현재 상태: {state} | full={full}, empty={empty}",
              {"isFull": full, "isEmpty": empty})


@app.route("/front", methods=["GET", "POST"])
def api_front():
    try:
        v = queue.peek()
        return ok("front", f"Front 데이터: {v}", v)
    except IndexError as e:
        return fail("front", str(e))


@app.route("/clear", methods=["GET", "POST"])
def api_clear():
    queue.clear()
    return ok("clear", "큐 전체 데이터 삭제 완료", None)


@app.route("/index", methods=["GET", "POST"])
def api_index():
    value, err = required_value("index")
    if err:
        return err
    pos = queue.positions(value)
    if pos:
        msg = f"{value}의 위치(Front 기준 index): {pos[0]}"
        if len(pos) > 1:
            msg += f" (전체 위치: {pos})"
        return ok("index", msg, {"index": pos[0], "positions": pos})
    return ok("index", f"{value}은(는) 큐에 없음 (index = -1)", {"index": -1, "positions": []})


@app.route("/count", methods=["GET", "POST"])
def api_count():
    value, err = required_value("count")
    if err:
        return err
    c = queue.count_of(value)
    return ok("count", f"{value}의 개수: {c}", c)


@app.route("/contains", methods=["GET", "POST"])
def api_contains():
    value, err = required_value("contains")
    if err:
        return err
    exists = queue.contains(value)
    return ok("contains", f"{value} 존재 여부: {'있음' if exists else '없음'} ({exists})", exists)


@app.route("/list", methods=["GET", "POST"])
def api_list():
    items = queue.items()
    return ok("list", f"Front → Rear ({len(items)}개): {items}", items)


@app.route("/state", methods=["GET"])
def api_state():
    return jsonify({"ok": True, "queue": queue.snapshot(), "history": history[-20:]})


# ---------------------------------------------------------------
# 서버 동작 상태 화면 (브라우저로 서버 URL 접속 시)
# ---------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    s = queue.snapshot()
    cells = ""
    for i, v in enumerate(s["array"]):
        mark = ""
        if i == s["frontIndex"]:
            mark += "F"
        if i == s["rearIndex"]:
            mark += "R"
        bg = "#dbeafe" if v is not None else "#f3f4f6"
        cells += (f"<td style='background:{bg}'><div class='i'>{i}</div>"
                  f"<div class='v'>{'' if v is None else v}</div><div class='m'>{mark}</div></td>")
    rows = "".join(
        f"<tr><td>{h['time']}</td><td>{h['action']}</td>"
        f"<td style='color:{'#15803d' if h['ok'] else '#b91c1c'}'>{h['message']}</td></tr>"
        for h in reversed(history[-20:])
    ) or "<tr><td colspan=3>아직 요청이 없습니다.</td></tr>"
    state = "FULL" if s["isFull"] else ("EMPTY" if s["isEmpty"] else "NORMAL")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3"><title>Fixed-Size Queue Server</title>
<style>
body{{font-family:sans-serif;margin:24px;color:#111}}
.badge{{display:inline-block;padding:4px 10px;border-radius:12px;background:#16a34a;color:#fff}}
table{{border-collapse:collapse;margin-top:8px}} td,th{{border:1px solid #ccc;padding:6px 8px;text-align:center}}
.i{{font-size:11px;color:#888}} .v{{font-weight:bold;min-width:28px}} .m{{font-size:11px;color:#dc2626}}
</style></head><body>
<h2>Fixed-Size Queue Server (Cloud Run) <span class="badge">RUNNING</span></h2>
<p>크기: <b>{s['capacity']}</b> | 데이터 개수: <b>{s['size']}</b> | 상태: <b>{state}</b>
 | Front index: {s['frontIndex']} | Rear index: {s['rearIndex']}</p>
<p>Front → Rear: {s['items']}</p>
<table><tr>{cells}</tr></table>
<p style="font-size:12px;color:#666">F = Front, R = Rear · 3초마다 자동 새로고침</p>
<h3>최근 요청 기록</h3>
<table><tr><th>시간(KST)</th><th>동작</th><th>결과</th></tr>{rows}</table>
</body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
