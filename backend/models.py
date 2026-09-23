from pydantic import BaseModel
from typing import Optional

# --- ADMIN & SERVICE MODELS ---

class AdminLoginReq(BaseModel):
    username: str
    password: str

class AdminUserBalanceReq(BaseModel):
    amount: int
    mode: Optional[str] = "delta"  # "delta" or "set"

class AdminDeviceSpeedLimitReq(BaseModel):
    speed_limit_mbps: int

class ServiceControlReq(BaseModel):
    service: str
    action: str

class FsWriteReq(BaseModel):
    path: str
    content: str

class VaultNotesReq(BaseModel):
    content: str


# --- TOKEN MODELS ---

class TokenGenerateReq(BaseModel):
    label: Optional[str] = ""

class TokenLabelReq(BaseModel):
    label: str

class TokenSpeedLimitReq(BaseModel):
    speed_limit_mbps: int

class TokenUpdateReq(BaseModel):
    label: Optional[str] = None
    is_active: Optional[bool] = None
    speed_limit_mbps: Optional[int] = None

class TokenActivateReq(BaseModel):
    token: str
    device_id: str
    device_model: Optional[str] = "Android Device"

class TokenReportReq(BaseModel):
    token: str
    device_id: str
    bytes_up: int
    bytes_down: int

class Hy2AuthReq(BaseModel):
    addr: Optional[str] = ""
    auth: Optional[str] = ""
    tx: Optional[int] = 0


# --- USER PROFILE & EMAIL AUTH MODELS ---

class EmailSendOtpReq(BaseModel):
    email: str

class EmailVerifyOtpReq(BaseModel):
    email: str
    code: str
    ref_code: Optional[str] = None
    platform: Optional[str] = None
    device_id: Optional[str] = None

class RegisterSendOtpReq(BaseModel):
    email: str
    agree_terms: bool
    agree_privacy: bool

class RegisterVerifyOtpReq(BaseModel):
    email: str
    code: str

class RegisterCompleteReq(BaseModel):
    email: str
    reg_token: str
    nickname: str
    password: str
    confirm_password: str
    ref_code: Optional[str] = None
    platform: Optional[str] = None
    device_id: Optional[str] = None

class UserLoginReq(BaseModel):
    email: str
    password: str
    platform: Optional[str] = None
    device_id: Optional[str] = None

class ResetPasswordSendOtpReq(BaseModel):
    email: str

class ResetPasswordCompleteReq(BaseModel):
    email: str
    code: str
    new_password: str

class DeleteAccountCompleteReq(BaseModel):
    code: str

class TariffChangeReq(BaseModel):
    plan: str  # 'base' or 'premium'

class ProfileTopUpReq(BaseModel):
    amount: int

class ProfileNicknameReq(BaseModel):
    nickname: str

class ProfileDeviceAddReq(BaseModel):
    device_name: Optional[str] = None
    name: Optional[str] = None
    tariff_plan: Optional[str] = "base"

class ProfileDeviceTariffReq(BaseModel):
    tariff_plan: str

class ProfileDeviceLimitReq(BaseModel):
    device_limit: int  # 1 to 5


# --- REVIEWS & SUPPORT MODELS ---

class ReviewSubmitReq(BaseModel):
    rating: int = 5
    text: str
    platform: Optional[str] = "Клиент Tabis"

class SupportClientMsgReq(BaseModel):
    session_token: str
    message: str
    page_url: Optional[str] = ""

class SupportAdminReplyReq(BaseModel):
    text: str

class SupportStatusReq(BaseModel):
    status: str

class TokenReportReq(BaseModel):
    token: str
    device_id: str
    bytes_up: int
    bytes_down: int

class Hy2AuthReq(BaseModel):
    addr: Optional[str] = ""
    auth: Optional[str] = ""
    tx: Optional[int] = 0
