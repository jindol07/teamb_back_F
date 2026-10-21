# D:/finalProjectB/back/apcms_ai/ai_vision/recognition/remote_plate_reader.py

"""현장 차량 영역을 Vision API로 보내 번호판 표본 하나를 받습니다."""

import math
from urllib.parse import urlsplit

import cv2
import numpy as np
import requests
from requests.adapters import HTTPAdapter

from ai_vision.upload_policy import MAX_UPLOAD_BYTES, MAX_IMAGE_PIXELS
from ai_vision.recognition.local_io import decode_object
from ai_vision.recognition.plate_review import KOREAN_PLATE_PATTERN, plate_review_reasons


class RemotePlateError(RuntimeError):
    """원격 인식 실패 시 현재 세션을 중단하기 위한 고정 오류 코드."""


class RemotePlateReader:
    def __init__(self, base_url, timeout=120, session_factory=None):
        if not isinstance(base_url, str):
            raise ValueError("Vision API 주소를 지정합니다.")
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or
                parsed.password is not None or parsed.query or parsed.fragment or
                any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in base_url)):
            raise ValueError("인증정보·쿼리 없는 Vision API 주소가 필요합니다.")
        parsed.port
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("원격 인식 제한 시간은 0초 초과 300초 이하입니다.")
        self._url, self._timeout = base_url.rstrip("/") + "/recognize", timeout
        self._session_factory = requests.Session if session_factory is None else session_factory

    def read(self, crop):
        # 1. 영상 전체 대신 추적한 차량 영역만 PNG로 전송합니다. 파일로 저장하지 않습니다.
        if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim != 3 or
                crop.shape[2] != 3 or not crop.size or crop.shape[0] * crop.shape[1] > MAX_IMAGE_PIXELS):
            raise ValueError("BGR uint8 차량 이미지가 필요합니다.")
        ok, encoded = cv2.imencode(".png", crop)
        if not ok or len(encoded) > MAX_UPLOAD_BYTES:
            raise ValueError("차량 이미지의 인코딩·업로드 한도를 확인합니다.")
        session = response = None
        try:
            session = self._session_factory()
            session.trust_env = False
            for protocol in ("http://", "https://"):
                session.mount(protocol, HTTPAdapter(max_retries=0))
            # 2. Boot API 키를 전달하지 않습니다. 원격 인식도 자동 재시도하지 않습니다.
            response = session.post(self._url, files={"file": ("vehicle.png", encoded.tobytes(), "image/png")},
                                    timeout=(3, self._timeout), allow_redirects=False, stream=True)
            if response.status_code != 200:
                raise RemotePlateError("REMOTE_HTTP_STATUS")
            raw = bytearray()
            for chunk in response.iter_content(8192):
                if not isinstance(chunk, bytes) or len(raw) + len(chunk) > 1024 * 1024:
                    raise ValueError("응답 크기·자료형 오류")
                raw.extend(chunk)
            return self._sample(decode_object(bytes(raw).decode("utf-8-sig")))
        except RemotePlateError:
            raise
        except requests.Timeout:
            raise RemotePlateError("REMOTE_TIMEOUT") from None
        except requests.RequestException:
            raise RemotePlateError("REMOTE_CONNECTION_FAILED") from None
        except Exception:
            raise RemotePlateError("REMOTE_INVALID_RESPONSE") from None
        finally:
            for resource in (response, session):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass

    @staticmethod
    def _sample(body):
        count, vehicles = body.get("vehicle_count"), body.get("vehicles")
        if (type(count) is not int or type(body.get("success")) is not bool or
                not isinstance(vehicles, list) or len(vehicles) != count or body["success"] != bool(count)):
            raise ValueError("차량 응답 형식 오류")
        if count == 0:
            return {"plate_number": "", "plate_type": "NOT_DETECTED"}
        # 3. 여러 차량을 한 추적 ID의 번호판으로 임의 선택하지 않습니다.
        if count != 1:
            raise RemotePlateError("REMOTE_AMBIGUOUS_VEHICLES")
        vehicle = vehicles[0]
        if not isinstance(vehicle, dict):
            raise ValueError("차량 응답 필드 오류")
        text, kind = vehicle.get("plate_number"), vehicle.get("plate_type")
        if (not isinstance(text, str) or len(text) > 128 or
                kind not in ("KOREAN_VALID", "REVIEW", "FOREIGN_OR_OTHER", "OCR_FAILED", "NOT_DETECTED", "CROP_FAILED")):
            raise ValueError("번호판 응답 필드 오류")
        sample = {"plate_number": text, "plate_type": kind, "review_reasons": plate_review_reasons(text, kind)}
        confidence = vehicle.get("plate_confidence")
        if kind == "KOREAN_VALID":
            if (not KOREAN_PLATE_PATTERN.fullmatch(text) or type(confidence) not in (int, float) or
                    not math.isfinite(confidence) or not 0 <= confidence <= 1):
                raise ValueError("번호판 형식·탐지 점수 불일치")
            sample["plate_detection_confidence"] = confidence
        return sample
