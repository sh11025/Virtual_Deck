"""
아이콘 자동 가져오기
- 프로그램 / 파일 / 폴더: Windows가 보여 주는 아이콘을 그대로 가져옵니다.
- 웹사이트: 그 사이트의 아이콘(파비콘)을 인터넷에서 받아옵니다.
가져온 아이콘은 data/icons 폴더에 저장됩니다.
"""

import os
import hashlib
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal, QFileInfo, QUrl, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core import paths


def extract_file_icon(path: str) -> str:
    """파일/폴더/프로그램의 아이콘을 PNG로 저장하고 저장 경로를 돌려줍니다. 실패하면 ''."""
    clean = (path or "").strip().strip("\"'")
    if not clean or not os.path.exists(clean):
        return ""
    try:
        icon = QFileIconProvider().icon(QFileInfo(clean))
        if icon.isNull():
            return ""
        pix = icon.pixmap(QSize(128, 128))
        if pix.isNull() or pix.width() < 8:
            return ""
        base = paths.safe_file_name(os.path.splitext(os.path.basename(clean.rstrip("\\/")))[0] or "folder")
        tag = hashlib.md5(clean.lower().encode("utf-8")).hexdigest()[:6]
        target = os.path.join(paths.icons_dir(), f"{base}_{tag}.png")
        pix.save(target, "PNG")
        return paths.to_stored_icon(target)
    except Exception:
        return ""


class FaviconFetcher(QObject):
    """웹사이트 아이콘을 비동기로 받아옵니다. 완료되면 done(저장 경로 또는 '') 신호."""

    done = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply = None
        self._host = ""

    def fetch(self, url: str) -> bool:
        text = (url or "").strip()
        if not text:
            return False
        if "://" not in text:
            text = "https://" + text
        host = urlparse(text).hostname
        if not host:
            return False
        self._host = host
        req = QNetworkRequest(QUrl(f"https://www.google.com/s2/favicons?domain={host}&sz=128"))
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.NoLessSafeRedirectPolicy)
        req.setTransferTimeout(6000)
        if self._reply is not None:
            # 이전 요청은 결과를 버리도록 연결을 끊고 취소(done("") 방지)
            old = self._reply
            self._reply = None
            try:
                old.finished.disconnect(self._on_finished)
            except (RuntimeError, TypeError):
                pass
            old.abort()
            old.deleteLater()
        self._reply = self._nam.get(req)
        self._reply.finished.connect(self._on_finished)
        return True

    def _on_finished(self) -> None:
        reply = self.sender()
        result = ""
        try:
            if reply.error() == QNetworkReply.NoError:
                img = QImage.fromData(bytes(reply.readAll()))
                if not img.isNull() and img.width() >= 16:
                    target = os.path.join(paths.icons_dir(), f"web_{paths.safe_file_name(self._host)}.png")
                    img.save(target, "PNG")
                    result = paths.to_stored_icon(target)
        finally:
            reply.deleteLater()
            if reply is self._reply:
                self._reply = None
        self.done.emit(result)
