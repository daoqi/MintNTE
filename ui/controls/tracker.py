from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtGui import QCursor

class GlobalMouseTracker(QObject):
    def __init__(self, overlay, main_window):
        super().__init__(main_window)
        self.overlay = overlay
        self.main_window = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            global_pos = QCursor.pos()
            if self.main_window.geometry().contains(global_pos):
                local_pos = self.overlay.mapFromGlobal(global_pos)
                self.overlay.mouse_pos = local_pos
                if not self.overlay.mouse_inside:
                    self.overlay.mouse_inside = True
            else:
                if self.overlay.mouse_inside:
                    self.overlay.mouse_inside = False
                    self.overlay.particles.clear()
                    self.overlay.update()
            return False
        return super().eventFilter(obj, event)