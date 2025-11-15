from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF
import math

class Runway_Approach(QWidget):
    def __init__(self, parent=None):
        super(Runway_Approach, self).__init__(parent)
        self.rows = 0
        self.cols = 0
        self.refresh_hz = 0
        self.airport_key = ""
        self.maxoffset_ft = 0

        self.current_airport_ID = ""
        self.runway_id_text = ""
        self.heading = 0
        self.vertical_speed = 0
        self.barometric_altitude = 0
        self.gps_altitude = 0
        self.gps_track = 0
        self.imu_data = {}

        self.runway_info = {}
        self.approach_data = {}

        self.initUI()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000 // self.refresh_hz)

    def initUI(self):
        self.layout = QVBoxLayout()
        self.airport_label = QLabel(self)
        self.runway_label = QLabel(self)
        self.layout.addWidget(self.airport_label)
        self.layout.addWidget(self.runway_label)
        self.setLayout(self.layout)

    def get_approach_data(self):
        # Placeholder for the function to obtain input data
        # MAVLink messages required: ATTITUDE, VFR_HUD, GPS_RAW_INT, SCALED_IMU2
        return {
            "heading": self.heading,
            "vertical_speed": self.vertical_speed,
            "barometric_altitude": self.barometric_altitude,
            "gps_altitude": self.gps_altitude,
            "gps_track": self.gps_track,
            "imu_data": self.imu_data
        }

    def get_runway_info(self):
        # Placeholder for the function to obtain runway info
        return self.runway_info

    def update_display(self):
        self.approach_data = self.get_approach_data()
        self.runway_info = self.get_runway_info()

        self.airport_label.setText(self.current_airport_ID)
        self.runway_label.setText(self.runway_id_text)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw heading arrow
        painter.setPen(QPen(QColor(Qt.GlobalColor.white), 2))
        arrow_length = self.height() * 0.75
        arrow_end = QPointF(self.width() / 2, self.height() - arrow_length)
        painter.drawLine(self.width() / 2, self.height(), arrow_end.x(), arrow_end.y())
        painter.drawLine(arrow_end.x(), arrow_end.y(), arrow_end.x() - 10, arrow_end.y() + 20)
        painter.drawLine(arrow_end.x(), arrow_end.y(), arrow_end.x() + 10, arrow_end.y() + 20)

        # Draw runway rectangle
        runway_width = self.width() * 0.1
        runway_height = self.height() * 0.85
        runway_center = QPointF(self.width() / 2, self.height() / 2)
        painter.setPen(QPen(QColor(Qt.GlobalColor.white), 2))
        painter.setBrush(QColor(Qt.GlobalColor.red))
        painter.drawRect(runway_center.x() - runway_width / 2, runway_center.y() - runway_height / 2, runway_width / 2, runway_height)
        painter.setBrush(QColor(Qt.GlobalColor.green))
        painter.drawRect(runway_center.x(), runway_center.y() - runway_height / 2, runway_width / 2, runway_height)

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
