import pytest

pytest.importorskip('PySide6')
pytest.importorskip('pytestqt')

from PySide6.QtCore import Qt

from app.ui_main import MainWindow
from app.compare_manager import CompareManager, CompareResponse
from app.api_client import ApiClient


class DummySignal:
    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        self._cbs.append(cb)

    def emit(self):
        for cb in list(self._cbs):
            cb()


class DummyFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class DummyWatcher:
    def __init__(self):
        self.finished = DummySignal()
        self._future = None

    def setFuture(self, fut):
        self._future = fut
        self.finished.emit()

    def result(self):
        return self._future.result()


class DummyProgress:
    def __init__(self, *a, **kw):
        pass

    def setWindowTitle(self, *a):
        pass

    def setWindowModality(self, *a):
        pass

    def setCancelButton(self, *a):
        pass

    def show(self):
        pass

    def close(self):
        pass


def fake_qt_run(fn, *a, **kw):
    return DummyFuture(fn(*a, **kw))


async def fake_acompare(*args, **kwargs):
    return CompareResponse(result='ok')


def test_gui_compare(monkeypatch, qtbot, tmp_path):
    manager = CompareManager(ApiClient('http://x', 'k'))
    monkeypatch.setattr(manager, 'load_json', lambda p: {})
    monkeypatch.setattr(manager, 'acompare', fake_acompare)

    import app.ui_main as ui
    monkeypatch.setattr(ui, 'QFutureWatcher', DummyWatcher)
    monkeypatch.setattr(ui, 'qt_run', fake_qt_run)
    monkeypatch.setattr(ui, 'QProgressDialog', DummyProgress)

    win = ui.MainWindow(manager)
    qtbot.addWidget(win)

    inp = tmp_path / 'i.json'
    ref = tmp_path / 'r.json'
    inp.write_text('{}')
    ref.write_text('{}')

    win.input_edit.setText(str(inp))
    win.ref_edit.setText(str(ref))

    qtbot.mouseClick(win.compare_btn, Qt.LeftButton)

    assert win.viewer.toPlainText() == 'ok'
