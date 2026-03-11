"""Main GUI window for the Polymarket BTC Bayesian Trading Bot."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import AppSettings, TradingMode
from app.gui.theme import DARK_STYLESHEET
from app.services.bot_controller import BotController, BotState


class SignalBridge(QObject):
    """Thread-safe bridge from async callbacks to Qt signals."""
    update_signal = Signal(str, dict)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, bot: BotController):
        super().__init__()
        self.settings = settings
        self.bot = bot
        self._bridge = SignalBridge()
        self._bridge.update_signal.connect(self._on_bot_event)
        self.bot.on_update(self._bridge_callback)

        self.setWindowTitle("Polymarket BTC Bayesian Bot")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        self._build_ui()
        self._start_refresh_timer()

    def _bridge_callback(self, event: str, data: dict):
        self._bridge.update_signal.emit(event, data)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header row ──
        header_row = QHBoxLayout()
        title = QLabel("Polymarket BTC Bayesian Bot")
        title.setObjectName("header")
        header_row.addWidget(title)
        header_row.addStretch()

        self._mode_badge = QLabel(self.settings.trading_mode.value.upper())
        self._mode_badge.setObjectName(
            "badge_paper" if not self.settings.is_live else "badge_live"
        )
        header_row.addWidget(self._mode_badge)
        root.addLayout(header_row)

        # ── Top controls row ──
        ctrl_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Bot")
        self._start_btn.clicked.connect(self._on_start)
        ctrl_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Bot")
        self._stop_btn.setObjectName("stop_btn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self._stop_btn)

        ctrl_row.addSpacing(20)
        self._state_label = QLabel("STOPPED")
        self._state_label.setObjectName("value")
        ctrl_row.addWidget(QLabel("Status:"))
        ctrl_row.addWidget(self._state_label)

        ctrl_row.addSpacing(20)
        self._bankroll_label = QLabel(f"${self.settings.initial_bankroll:.2f}")
        self._bankroll_label.setObjectName("value")
        ctrl_row.addWidget(QLabel("Bankroll:"))
        ctrl_row.addWidget(self._bankroll_label)

        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        # ── Main content area ──
        splitter = QSplitter(Qt.Vertical)

        # Upper: Signal + Decision panels
        upper = QWidget()
        upper_lay = QHBoxLayout(upper)
        upper_lay.setContentsMargins(0, 0, 0, 0)
        upper_lay.setSpacing(8)

        upper_lay.addWidget(self._build_signal_panel(), 3)
        upper_lay.addWidget(self._build_decision_panel(), 3)
        upper_lay.addWidget(self._build_health_panel(), 2)
        splitter.addWidget(upper)

        # Lower: Tabs for orders, fills, log console, settings
        tabs = QTabWidget()
        tabs.addTab(self._build_orders_tab(), "Active Orders")
        tabs.addTab(self._build_fills_tab(), "Recent Fills")
        tabs.addTab(self._build_log_tab(), "Log Console")
        tabs.addTab(self._build_settings_tab(), "Settings")
        splitter.addWidget(tabs)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

    # ── Panel builders ──────────────────────────────────────

    def _build_signal_panel(self) -> QGroupBox:
        box = QGroupBox("Signals")
        lay = QVBoxLayout(box)

        self._sig_market = self._kv_row(lay, "Market", "—")
        self._sig_btc = self._kv_row(lay, "BTC Price", "—")
        self._sig_vwap_z = self._kv_row(lay, "VWAP Z-Score", "—")
        self._sig_vwap_dir = self._kv_row(lay, "VWAP Direction", "—")
        self._sig_funding_z = self._kv_row(lay, "Funding Z-Score", "—")
        self._sig_funding_dir = self._kv_row(lay, "Funding Direction", "—")
        self._sig_rvol = self._kv_row(lay, "RVOL", "—")
        self._sig_rvol_dir = self._kv_row(lay, "RVOL Direction", "—")
        self._sig_agreement = self._kv_row(lay, "Agreement", "—")

        lay.addStretch()
        return box

    def _build_decision_panel(self) -> QGroupBox:
        box = QGroupBox("Bayesian Model")
        lay = QVBoxLayout(box)

        self._dec_prior = self._kv_row(lay, "Prior (UP)", "—")
        self._dec_lr_vwap = self._kv_row(lay, "LR VWAP", "—")
        self._dec_lr_funding = self._kv_row(lay, "LR Funding", "—")
        self._dec_lr_rvol = self._kv_row(lay, "LR RVOL", "—")
        self._dec_raw_post = self._kv_row(lay, "Raw Posterior", "—")
        self._dec_cal_post = self._kv_row(lay, "Calibrated Posterior", "—")
        self._dec_mkt_implied = self._kv_row(lay, "Market Implied", "—")
        self._dec_edge = self._kv_row(lay, "Edge", "—")
        self._dec_should = self._kv_row(lay, "Should Trade", "—")
        self._dec_blocked = self._kv_row(lay, "Blocked Reason", "—")
        self._dec_macro = self._kv_row(lay, "Macro Veto", "—")

        lay.addStretch()
        return box

    def _build_health_panel(self) -> QGroupBox:
        box = QGroupBox("Health")
        lay = QVBoxLayout(box)

        self._health_binance_ws = self._kv_row(lay, "Binance WS", "—")
        self._health_binance_rest = self._kv_row(lay, "Binance REST", "—")
        self._health_polymarket = self._kv_row(lay, "Polymarket", "—")
        self._health_database = self._kv_row(lay, "Database", "—")
        self._health_calibration = self._kv_row(lay, "Calibration", "—")

        lay.addStretch()
        return box

    def _build_orders_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._orders_table = QTableWidget(0, 7)
        self._orders_table.setHorizontalHeaderLabels(
            ["Time", "Market", "Side", "Price", "Size", "Status", "Order ID"]
        )
        self._orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self._orders_table)
        return w

    def _build_fills_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._fills_table = QTableWidget(0, 7)
        self._fills_table.setHorizontalHeaderLabels(
            ["Time", "Market", "Direction", "Price", "Size", "Fee", "Slippage"]
        )
        self._fills_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self._fills_table)
        return w

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._log_console = QTextEdit()
        self._log_console.setReadOnly(True)
        lay.addWidget(self._log_console)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        info_pairs = [
            ("Trading Mode", self.settings.trading_mode.value),
            ("Min Edge Threshold", str(self.settings.min_edge_threshold)),
            ("Max Fraction/Trade", str(self.settings.max_fraction_per_trade)),
            ("Max Daily Loss", f"${self.settings.max_daily_loss}"),
            ("Max Open Exposure", f"${self.settings.max_open_exposure}"),
            ("Max Concurrent Markets", str(self.settings.max_concurrent_markets)),
            ("Kelly Fraction", str(self.settings.kelly_fraction)),
            ("Execution Style", self.settings.execution_style.value),
            ("Stale Order Timeout", f"{self.settings.stale_order_timeout_seconds}s"),
            ("Fee Rate", str(self.settings.fee_rate)),
            ("Macro Veto Before", f"{self.settings.macro_veto_before_minutes} min"),
            ("Macro Veto After", f"{self.settings.macro_veto_after_minutes} min"),
            ("VWAP Lookback (med)", f"{self.settings.vwap_lookback_medium}s"),
        ]
        for label, val in info_pairs:
            self._kv_row(lay, label, val)
        lay.addStretch()
        return w

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _kv_row(layout: QVBoxLayout, key: str, default: str) -> QLabel:
        row = QHBoxLayout()
        key_label = QLabel(key + ":")
        key_label.setFixedWidth(160)
        key_label.setStyleSheet("color: #8b949e;")
        val_label = QLabel(default)
        val_label.setObjectName("value")
        row.addWidget(key_label)
        row.addWidget(val_label)
        row.addStretch()
        layout.addLayout(row)
        return val_label

    def _start_refresh_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.settings.gui_refresh_interval_ms)

    # ── Slots / updates ────────────────────────────────────

    @Slot()
    def _tick(self):
        self._bankroll_label.setText(f"${self.bot.bankroll:.2f}")
        self._state_label.setText(self.bot.state.upper())

        health = self.bot.health.summary()
        self._update_health("binance_ws", self._health_binance_ws, health)
        self._update_health("binance_rest", self._health_binance_rest, health)
        self._update_health("polymarket", self._health_polymarket, health)
        self._update_health("database", self._health_database, health)
        self._update_health("calibration", self._health_calibration, health)

    @staticmethod
    def _update_health(key: str, label: QLabel, health: dict):
        status = health.get(key, "unknown")
        label.setText(status.upper())
        if status == "ok":
            label.setObjectName("status_ok")
        else:
            label.setObjectName("status_down")
        label.setStyleSheet(label.styleSheet())

    @Slot(str, dict)
    def _on_bot_event(self, event: str, data: dict):
        if event == "state_change":
            state = data.get("state", "")
            self._state_label.setText(state.upper())
            running = state == BotState.RUNNING
            self._start_btn.setEnabled(not running)
            self._stop_btn.setEnabled(running)

        elif event == "decision":
            self._update_decision(data)

        elif event == "cycle":
            feat = data.get("features")
            if feat and hasattr(feat, "vwap") and feat.vwap:
                self._update_signals(feat)

        elif event == "fill":
            self._add_fill_row(data)

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._log_console.append(f"[{ts}] {event}: {data}")

    def _update_signals(self, feat):
        if feat.vwap:
            self._sig_btc.setText(f"${feat.vwap.btc_price:,.2f}")
            self._sig_vwap_z.setText(f"{feat.vwap.zscore:.4f}")
            self._set_direction(self._sig_vwap_dir, feat.vwap.direction)
        if feat.funding:
            self._sig_funding_z.setText(f"{feat.funding.zscore:.4f}")
            self._set_direction(self._sig_funding_dir, feat.funding.direction)
        if feat.rvol:
            self._sig_rvol.setText(f"{feat.rvol.rvol:.3f}")
            self._set_direction(self._sig_rvol_dir, feat.rvol.direction)

        agreed = feat.agreed_direction
        self._sig_agreement.setText(agreed.upper() if agreed else "NONE")
        if agreed:
            self._set_direction(self._sig_agreement, agreed)
        else:
            self._sig_agreement.setObjectName("signal_neutral")

    def _update_decision(self, data: dict):
        self._sig_market.setText(data.get("market", "—"))
        self._dec_prior.setText(f"{data.get('prior_up', 0):.4f}")
        self._dec_lr_vwap.setText(f"{data.get('lr_vwap', 0):.3f}")
        self._dec_lr_funding.setText(f"{data.get('lr_funding', 0):.3f}")
        self._dec_lr_rvol.setText(f"{data.get('lr_rvol', 0):.3f}")
        self._dec_raw_post.setText(f"{data.get('raw_posterior', 0):.4f}")
        self._dec_cal_post.setText(f"{data.get('calibrated_posterior', 0):.4f}")
        self._dec_mkt_implied.setText(f"{data.get('market_implied', 0):.4f}")

        edge = data.get("edge", 0)
        self._dec_edge.setText(f"{edge:.4f}")
        if abs(edge) >= self.settings.min_edge_threshold:
            self._dec_edge.setStyleSheet("color: #3fb950; font-weight: bold;")
        else:
            self._dec_edge.setStyleSheet("color: #8b949e;")

        should = data.get("should_trade", False)
        self._dec_should.setText("YES" if should else "NO")
        self._dec_should.setStyleSheet(
            "color: #3fb950; font-weight: bold;" if should
            else "color: #da3633;"
        )
        self._dec_blocked.setText(data.get("blocked_reason", "—") or "—")
        self._dec_macro.setText("ACTIVE" if data.get("macro_veto") else "CLEAR")
        if data.get("macro_veto"):
            self._dec_macro.setStyleSheet("color: #da3633; font-weight: bold;")
        else:
            self._dec_macro.setStyleSheet("color: #3fb950;")

    def _add_fill_row(self, data: dict):
        row = self._fills_table.rowCount()
        self._fills_table.insertRow(row)
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        vals = [
            ts,
            data.get("market", ""),
            data.get("direction", ""),
            f"{data.get('price', 0):.4f}",
            f"{data.get('size', 0):.2f}",
            "—",
            "—",
        ]
        for col, v in enumerate(vals):
            self._fills_table.setItem(row, col, QTableWidgetItem(v))

    @staticmethod
    def _set_direction(label: QLabel, direction: str):
        label.setText(direction.upper())
        if direction == "up":
            label.setObjectName("signal_up")
        elif direction == "down":
            label.setObjectName("signal_down")
        else:
            label.setObjectName("signal_neutral")
        label.setStyleSheet(label.styleSheet())

    # ── Button handlers ────────────────────────────────────

    @Slot()
    def _on_start(self):
        self._log_console.append("[GUI] Starting bot...")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(self.bot.start())
        else:
            loop.run_until_complete(self.bot.start())

    @Slot()
    def _on_stop(self):
        self._log_console.append("[GUI] Stopping bot...")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(self.bot.stop())
        else:
            loop.run_until_complete(self.bot.stop())
