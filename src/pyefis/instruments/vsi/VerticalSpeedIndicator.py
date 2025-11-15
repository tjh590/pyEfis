from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF
import math

class VerticalSpeedIndicator(QWidget):
    def __init__(self, parent=None):
        super(VerticalSpeedIndicator, self).__init__(parent)
        self.vertical_speed = 0
        self.kalman_filter = KalmanFilter()

        self.initUI()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)

    def initUI(self):
        self.layout = QVBoxLayout()
        self.vertical_speed_label = QLabel(self)
        self.layout.addWidget(self.vertical_speed_label)
        self.setLayout(self.layout)

    def update_display(self):
        self.vertical_speed = self.kalman_filter.get_filtered_value()
        self.vertical_speed_label.setText(f"Vertical Speed: {self.vertical_speed:.2f} ft/min")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw vertical speed indicator
        vsi_width = self.width() * 0.1
        vsi_height = self.height()
        vsi_center = QPointF(self.width() - vsi_width / 2, self.height() / 2)
        painter.setPen(QPen(QColor(Qt.GlobalColor.white), 2))
        painter.setBrush(QColor(Qt.GlobalColor.gray))
        painter.drawRect(vsi_center.x() - vsi_width / 2, vsi_center.y() - vsi_height / 2, vsi_width, vsi_height)
        painter.setBrush(QColor(Qt.GlobalColor.green))
        painter.drawRect(vsi_center.x() - vsi_width / 2, vsi_center.y() - 5, vsi_width, 10)
        painter.setBrush(QColor(Qt.GlobalColor.purple))
        vsi_value = self.vertical_speed / 1500 * vsi_height / 2
        painter.drawPolygon(QPolygonF([QPointF(vsi_center.x() - vsi_width / 2, vsi_center.y() - vsi_value),
                                       QPointF(vsi_center.x() + vsi_width / 2, vsi_center.y() - vsi_value),
                                       QPointF(vsi_center.x(), vsi_center.y() - vsi_value - 10)]))

class KalmanFilter:
    def __init__(self):
        self.x = 0  # state
        self.P = 1  # estimation error covariance
        self.Q = 0.1  # process noise covariance
        self.R = 1  # measurement noise covariance

    def update(self, measurement):
        # Prediction step
        self.x = self.x
        self.P = self.P + self.Q

        # Update step
        K = self.P / (self.P + self.R)
        self.x = self.x + K + (measurement - self.x)
        self.P = (1 - K) * self.P

    def get_filtered_value(self):
        return self.x
