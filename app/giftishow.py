# app/giftishow.py
"""기프티쇼 비즈 API 클라이언트 — 연동규격서 v1.04 기준"""

import requests
from typing import Dict, Any, Optional


class GiftishowError(Exception):
    pass


class GiftishowClient:
    """
    기프티쇼 비즈 API 클라이언트.

    Parameters
    ----------
    base_url : str
        API 베이스 URL (예: https://bizapi.giftishow.com/bizApi)
    custom_auth_code : str
        사이트 내 발급받은 인증Key (계정마다 Unique)
    custom_auth_token : str
        사이트 내 발급받은 Token Key
    user_id : str
        회원 ID
    dev_yn : str
        테스트여부 설정 값 (N 입력 — 현재 개발환경 미지원)
    """

    def __init__(
        self,
        base_url: str,
        custom_auth_code: str,
        custom_auth_token: str,
        user_id: str,
        dev_yn: str = "N",
    ):
        self.base_url = base_url.rstrip("/")
        self.custom_auth_code = custom_auth_code
        self.custom_auth_token = custom_auth_token
        self.user_id = user_id
        self.dev_yn = dev_yn or "N"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(
        self,
        endpoint: str,
        api_code: str,
        extra_data: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """
        공통 POST 요청.

        Parameters
        ----------
        endpoint : str
            API 경로 (예: "goods", "send")
        api_code : str
            API 코드 (예: "0101", "0204")
        extra_data : dict, optional
            추가 파라미터
        timeout : int
            요청 타임아웃 (초)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        payload: Dict[str, Any] = {
            "api_code": api_code,
            "custom_auth_code": self.custom_auth_code,
            "custom_auth_token": self.custom_auth_token,
            "dev_yn": self.dev_yn,
        }
        if extra_data:
            payload.update(extra_data)

        r = requests.post(url, data=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception as e:
            raise GiftishowError(f"Invalid JSON response: {e}")

    @staticmethod
    def _check_outer(resp: Dict[str, Any]) -> Dict[str, Any]:
        """최외곽 code 확인 후 result 반환."""
        code = str(resp.get("code", ""))
        if code not in ("0000",):
            msg = resp.get("message") or ""
            raise GiftishowError(f"API outer error [{code}]: {msg}")
        return resp

    # ------------------------------------------------------------------
    # 1. 상품 리스트 (API 0101)
    # ------------------------------------------------------------------

    def list_products(self, start: int = 1, size: int = 100) -> Dict[str, Any]:
        """
        상품 리스트 조회.

        URL: /bizApi/goods
        권장: 새벽 배치로 전체 리스트 저장
        """
        resp = self._post("goods", "0101", {"start": str(start), "size": str(size)})
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 2. 상품 상세 정보 (API 0111)
    # ------------------------------------------------------------------

    def get_product(self, goods_code: str) -> Dict[str, Any]:
        """
        개별 상품 상세 조회.

        URL: /bizApi/goods/{goods_code}
        """
        resp = self._post(f"goods/{goods_code}", "0111")
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 3. 브랜드 정보 조회 (API 0102)
    # ------------------------------------------------------------------

    def list_brands(self) -> Dict[str, Any]:
        """
        브랜드 리스트 조회.

        URL: /bizApi/brands
        """
        resp = self._post("brands", "0102")
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 4. 브랜드 상세 정보 (API 0112)
    # ------------------------------------------------------------------

    def get_brand(self, brand_code: str) -> Dict[str, Any]:
        """
        단일 브랜드 상세 조회.

        URL: /bizApi/brands/{brand_code}
        """
        resp = self._post(f"brands/{brand_code}", "0112")
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 5. 쿠폰 상세 정보 (API 0201)
    # ------------------------------------------------------------------

    def get_coupon(self, tr_id: str) -> Dict[str, Any]:
        """
        TR_ID로 쿠폰 상세정보 조회.

        URL: /bizApi/coupons
        """
        resp = self._post("coupons", "0201", {
            "tr_id": tr_id,
        })
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 6. 쿠폰 취소 (API 0202)
    # ------------------------------------------------------------------

    def cancel_coupon(self, tr_id: str) -> Dict[str, Any]:
        """
        오발송 등의 사유로 쿠폰 취소.

        URL: /bizApi/cancel
        주의: 1건씩 응답 받은 후 다음 건 요청
        """
        resp = self._post("cancel", "0202", {
            "tr_id": tr_id,
            "user_id": self.user_id,
        })
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 7. 쿠폰 재전송 (API 0203)
    # ------------------------------------------------------------------

    def resend_coupon(self, tr_id: str, sms_flag: str = "N") -> Dict[str, Any]:
        """
        MMS 삭제한 수신 고객에게 쿠폰 재전송.

        URL: /bizApi/resend
        주의: 고객 요청에 따라 사용 (일괄 전송 불가)
        """
        resp = self._post("resend", "0203", {
            "tr_id": tr_id,
            "user_id": self.user_id,
            "sms_flag": sms_flag,
        })
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 8. 쿠폰 발송 요청 (API 0204) — 핵심!
    # ------------------------------------------------------------------

    def send_coupon(
        self,
        tr_id: str,
        phone_no: str,
        goods_code: str,
        callback_no: str,
        gubun: str = "I",
        mms_title: str = "경품",
        mms_msg: str = "축하합니다!",
        order_no: Optional[str] = None,
        template_id: Optional[str] = None,
        banner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        쿠폰 발송 요청.

        URL: /bizApi/send
        gubun: Y=핀번호수신, N=MMS, I=바코드이미지수신
        주의:
          - TR_ID는 25자 이하, Unique
          - mms_title은 10자 이하
          - 타임아웃(15초) 시 동일 TR_ID로 쿠폰취소요청 필수
        """
        data: Dict[str, Any] = {
            "tr_id": tr_id,
            "phone_no": phone_no,
            "goods_code": goods_code,
            "callback_no": callback_no,
            "gubun": gubun,
            "mms_title": mms_title,
            "mms_msg": mms_msg,
            "user_id": self.user_id,
        }
        if order_no:
            data["order_no"] = order_no
        if template_id:
            data["template_id"] = template_id
        if banner_id:
            data["banner_id"] = banner_id

        resp = self._post("send", "0204", data, timeout=15)
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 9. 비즈머니 잔액 조회 (API 0301)
    # ------------------------------------------------------------------

    def get_bizmoney_balance(self) -> Dict[str, Any]:
        """
        현재 비즈머니 잔액 조회.

        URL: /bizApi/bizmoney
        """
        resp = self._post("bizmoney", "0301", {
            "user_id": self.user_id,
        })
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # 10. 발송실패 취소 (API 0205)
    # ------------------------------------------------------------------

    def cancel_send_fail(self, tr_id: str) -> Dict[str, Any]:
        """
        비즈머니 차감 되었으나 핀 미발행된 발송실패 건 취소.

        URL: /bizApi/sendFail/cancel
        주의: 일반 cancel(0202)과 다름 — 핀 미발행 건에만 사용
        """
        resp = self._post("sendFail/cancel", "0205", {
            "tr_id": tr_id,
            "user_id": self.user_id,
        })
        self._check_outer(resp)
        return resp

    # ------------------------------------------------------------------
    # Utility: 발송 응답에서 결과 추출
    # ------------------------------------------------------------------

    @staticmethod
    def parse_send_response(resp: Dict[str, Any]) -> Dict[str, Any]:
        """
        send_coupon 응답의 중첩 구조에서 결과를 추출.

        Returns dict with keys: outer_code, inner_code, order_no, pin_no, coupon_img_url
        """
        outer_code = str(resp.get("code", ""))
        outer_msg = resp.get("message") or ""

        inner = resp.get("result") or {}
        inner_code = str(inner.get("code", ""))
        inner_msg = inner.get("message") or ""

        result = inner.get("result") or {}
        return {
            "outer_code": outer_code,
            "outer_message": outer_msg,
            "inner_code": inner_code,
            "inner_message": inner_msg,
            "order_no": result.get("orderNo"),
            "pin_no": result.get("pinNo"),
            "coupon_img_url": result.get("couponImgUrl"),
        }
