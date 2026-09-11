from fastapi import FastAPI, HTTPException, Depends, Path, status
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="iBanking Tuition Payment API",
    description="API hệ đóng học phí của ứng dụng iBanking",
    version="1.0.0"
)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserProfileResponse(BaseModel):
    full_name: str
    phone: str
    email: str
    available_balance: float

class TuitionResponse(BaseModel):
    mssv: str
    student_name: str
    tuition_amount: float
    status: str

class InitiatePaymentRequest(BaseModel):
    mssv: str
    amount: float

class InitiatePaymentResponse(BaseModel):
    transaction_id: str
    message: str

class ConfirmPaymentRequest(BaseModel):
    otp: str

class TransactionResponse(BaseModel):
    message: str
    transaction_id: str
    status: str


async def get_current_user(token: str = "dummy_token"):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return {"user_id": 1, "username": "user123"}


@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(request: LoginRequest):
    """
    1. Đăng nhập và lấy thông tin Token
    """
    if request.username == "user123" and request.password == "password123":
        return {"access_token": "mock_jwt_token_12345", "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sai username hoặc password"
    )

@app.get("/api/v1/users/me", response_model=UserProfileResponse, tags=["User"])
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    2. Lấy thông tin tài khoản đang đăng nhập (Tự động load vào màn hình)
    """
    return {
        "full_name": "Nguyễn Văn A",
        "phone": "0901234567",
        "email": "nva@gmail.com",
        "available_balance": 50000000.0
    }

@app.get("/api/v1/students/{mssv}/tuition", response_model=TuitionResponse, tags=["Tuition"])
async def lookup_tuition(
    mssv: str = Path(..., title="Mã số sinh viên", min_length=5),
    current_user: dict = Depends(get_current_user)
):
    """
    3. Tra cứu thông tin học phí của sinh viên
    """
    if mssv == "51900001":
        return {
            "mssv": "51900001",
            "student_name": "Trần Thị B",
            "tuition_amount": 15000000.0,
            "status": "UNPAID"
        }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Không tìm thấy thông tin sinh viên"
    )

@app.post("/api/v1/payments/initiate", response_model=InitiatePaymentResponse, status_code=status.HTTP_201_CREATED, tags=["Payment"])
async def initiate_payment(
    request: InitiatePaymentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    4. Khởi tạo thanh toán, kiểm tra điều kiện và gửi OTP
    """
    mock_balance = 50000000.0
    if request.amount > mock_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số dư khả dụng không đủ để thực hiện giao dịch"
        )
    return {
        "transaction_id": "TXN_987654321",
        "message": "OTP đã được gửi đến email của bạn."
    }

@app.post("/api/v1/payments/{transaction_id}/confirm", response_model=TransactionResponse, tags=["Payment"])
async def confirm_payment(
    request: ConfirmPaymentRequest,
    transaction_id: str = Path(...),
    current_user: dict = Depends(get_current_user)
):
    """
    5. Nhập OTP để xác nhận và hoàn tất trừ tiền
    """
    if request.otp != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn"
        )
    
    return {
        "message": "Thanh toán học phí thành công",
        "transaction_id": transaction_id,
        "status": "SUCCESS"
    }