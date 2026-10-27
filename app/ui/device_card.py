# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""米家风格的设备卡片。

卡片承担两级操作：右侧圆形电源钮直接开关（快速路径），点击卡片本体
打开详情面板（完整控制）。布局为纯文字：左侧设备名与副标题（房间，
可附带温湿度读数），右侧垂直居中的电源钮，无装饰图标。

设备是否支持开关在列表接口里拿不到：电源钮初始隐藏，后台批量探测
确认有可写开关属性后才显示并回填真实状态。
"""

from pathlib import Path

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from app.siui.components.container import SiRowCard

from app.core.models import DeviceInfo
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors

_POWER_BTN_SIZE = 36
# 图标显示尺寸；占位与图片同宽，不留空白边
_ICON_SIZE = 32
# 卡片固定宽度与主窗口默认一排放几列联动（见 MainWindow._default_window_width），
# 调窄后默认窗口宽度下恰好 5 列
_CARD_FIXED_WIDTH = 200
_CARD_FIXED_HEIGHT = 92

# 离线卡片的灰置配色：背景更暗、文字更灰，hover 不提亮


class DeviceCard(SiRowCard):
    power_clicked = Signal(str)  # did
    open_requested = Signal(str)  # did

    def __init__(self, device: DeviceInfo, parent=None):
        super().__init__(parent, self.LeftToRight)
        self.device = device
        self._busy = False
        self._hovered = False
        self._online = device.online

        self.style_data.background_color = QColor(
            SiColors.OFFLINE_CARD if not self._online else SiColors.CARD)
        self.style_data.border_radius = 14.0
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # 固定尺寸：宽度固定，窗口缩放仅改变列数，卡片本身不被拉伸
        self.setFixedSize(_CARD_FIXED_WIDTH, _CARD_FIXED_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.muteStretchWidget()

        self._power_btn = PowerButton(_POWER_BTN_SIZE, icon_size=24)
        self._power_btn.clicked.connect(lambda: self.power_clicked.emit(device.did))
        # 列表接口不带开关信息，先隐藏电源钮；后台探测确认设备
        # 有可写开关属性后再显示并回填真实状态
        self._power_btn.hide()
        self._power_btn.set_online(self._online)

        name_color = SiColors.TEXT_PRIMARY if self._online else SiColors.OFFLINE_TEXT
        self._name_label = QLabel(device.name)
        self._name_label.setFont(QFont("Microsoft YaHei UI", 15, QFont.Weight.DemiBold))
        # 单行省略而不是换行：卡片高度固定，换行会把副标题和开关挤变形。
        # 水平方向忽略自身宽度诉求，交给布局按剩余空间分配。
        self._name_label.setWordWrap(False)
        self._name_label.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._name_label.setStyleSheet(
            f"color: {name_color}; background: transparent;")
        self._name_label.setToolTip(device.name)

        self._sub_label = QLabel(self._sub_text())
        self._sub_label.setFont(QFont("Microsoft YaHei UI", 11))
        sub_color = SiColors.TEXT_SECONDARY if self._online else SiColors.OFFLINE_SUB
        self._sub_label.setStyleSheet(
            f"color: {sub_color}; background: transparent;")
        # 离线卡片电源钮不可操作
        if not self._online:
            self._power_btn.setEnabled(False)

        # 设备图标：后台拉取就绪后由 set_icon 填入，未就绪前保持隐藏
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.hide()

        # 左侧文字列整体垂直居中，与右侧电源钮同一水平轴
        text_col = QWidget()
        text_col.setAttribute(Qt.WA_TranslucentBackground)
        # 文字列吃掉卡片剩余宽度，名称才有空间做省略而不是被挤成几个字
        text_col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_lay = QVBoxLayout(text_col)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(4)
        text_lay.addStretch(1)
        text_lay.addWidget(self._name_label)
        text_lay.addWidget(self._sub_label)
        text_lay.addStretch(1)

        lay = self.layout()
        # 左右边距与图标间距收紧，把宽度尽量留给设备名
        lay.setContentsMargins(12, 10, 14, 10)
        lay.addWidget(self._icon_label, alignment=Qt.AlignVCenter)
        lay.addSpacing(6)
        lay.addWidget(text_col, stretch=1)
        lay.addWidget(self._power_btn, alignment=Qt.AlignVCenter)
        # 构造时就按固定宽度算一次：部分场景（离屏渲染、还没布局）
        # 不会立刻收到 resizeEvent，先截好避免长名字露出完整内容
        self._update_elided_name()

    # ---------- 名称省略 ----------

    @staticmethod
    def _elide_two_lines(text: str, width: int, metrics) -> str:
        """把文本压到最多两行，放不下的部分在第二行末尾加省略号。

        QLabel 自身不支持多行省略，这里按字体度量逐字排：第一行尽量
        填满，第二行继续填，仍有剩余就用省略号收尾。
        """
        if width <= 0 or metrics.horizontalAdvance(text) <= width:
            return text
        first = ""
        index = 0
        while index < len(text) and metrics.horizontalAdvance(
                first + text[index]) <= width:
            first += text[index]
            index += 1
        if not first:
            # 宽度连一个字都放不下：至少留一个字符，避免只剩省略号
            first = text[:1]
            index = 1
        rest = text[index:]
        if not rest:
            return first
        second = ""
        while rest and metrics.horizontalAdvance(
                second + rest[0] + "…") <= width:
            second += rest[0]
            rest = rest[1:]
        return f"{first}\n{second}…"

    def _update_elided_name(self) -> None:
        """按标签实际可用宽度排设备名，最多两行，完整名称留在 tooltip。

        优先读标签自身宽度：卡片在不同列数下会被布局拉伸，用固定
        尺寸推算会和真实可用宽度对不上。布局还没结算时（宽度为 0）
        先放完整名字，等下一次 resize 或 show 再排。
        """
        icon_w = (_ICON_SIZE + 6) if self._icon_label.isVisible() else 0
        room = self.width() - 12 - 14 - icon_w - _POWER_BTN_SIZE
        # 取标签宽度与卡片剩余宽度的较小值：离屏渲染等场景下标签
        # 可能拿到超出卡片的宽度，直接用会把文字算成放得下
        width = min(self._name_label.width(), room)
        if width <= 0:
            self._name_label.setText(self.device.name)
            return
        self._name_label.setText(self._elide_two_lines(
            self.device.name, width, self._name_label.fontMetrics()))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        super().resizeEvent(event)
        self._update_elided_name()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        # 首次显示时布局才真正结算，此时补算一次才能拿到准确宽度
        super().showEvent(event)
        self._update_elided_name()

    # ---------- 状态渲染 ----------

    def set_icon(self, path: Path | None) -> None:
        """填入设备图标；路径无效或图片损坏时保持隐藏不打断布局。"""
        if path is None or not path.is_file():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._icon_label.setPixmap(pixmap.scaled(
            _ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self._icon_label.show()

    def set_power_state(self, state: bool) -> None:
        # 能设置状态即证明设备具备开关能力，电源钮随之可见
        self._power_btn.set_state(state)
        self._power_btn.show()

    def _sub_text(self, metrics: str | None = None) -> str:
        """副标题文案：离线优先显示离线标记，有读数时附带。"""
        base = self.device.room_name
        if not self._online:
            return f"{base} · 离线"
        if metrics:
            return f"{base} | {metrics}"
        return base

    def set_metrics(self, text: str | None) -> None:
        """副标题附带实时读数（温湿度等），离线卡片不叠加读数。"""
        # 离线设备不展示温湿度，读数可能是旧缓存
        if not self._online:
            return
        self._sub_label.setText(self._sub_text(text))

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._power_btn.set_busy(busy)

    # ---------- hover 观感 ----------

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        self._hovered = True
        self._apply_card_color()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        self._hovered = False
        self._apply_card_color()
        super().leaveEvent(event)

    def _apply_card_color(self) -> None:
        if not self._online:
            # 离线卡片整体灰置，hover 不提亮（无交互暗示）
            self.style_data.background_color = QColor(SiColors.OFFLINE_CARD)
        else:
            self.style_data.background_color = QColor(
                SiColors.CARD_HOVER if self._hovered else SiColors.CARD
            )
        self.update()

    # ---------- 交互 ----------

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        # 电源钮自己消费点击事件，能走到这里的都是卡片空白区
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.device.did)
        super().mouseReleaseEvent(event)


