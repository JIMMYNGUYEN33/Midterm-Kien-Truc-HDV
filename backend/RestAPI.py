from datetime import datetime, timedelta
import random
import uuid
from fastapi import FastAPI, Depends, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Numeric, String, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# --- CẤU HÌNH KẾT NỐI POSTGRESQL TRONG DOCKER ---
DATABASE_URL = "postgresql://root:rootpassword@db:5432/ibanking"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(
    title="iBanking Tuition Payment API",
    description="API hệ thống đóng học phí iBanking - Phân công Gia Phúc",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SQLAlchemy Models (Khớp 100% ERD trong init.sql) ---
class UserModel(Base):
    __tablename__ = "NguoiDung"
    MaNguoiDung = Column(Integer, primary_key=True, index=True)
    TenDangNhap = Column(String(50), unique=True, nullable=False)
    MatKhau = Column(String(255), nullable=False)
    HoTen = Column(String(100), nullable=False)
    Email = Column(String(100), nullable=False)
    SoDuKhaDung = Column(Numeric(15, 2), nullable=False)

class SinhVienModel(Base):
    __tablename__ = "SinhVien"
    MSSV = Column(String(20), primary_key=True)
    HoTen = Column(String(100), nullable=False)
    Email = Column(String(100))
    SoDienThoai = Column(String(20))

class HocPhiModel(Base):
    __tablename__ = "HocPhi"
    MaHocPhi = Column(Integer, primary_key=True, index=True)
    MSSV = Column(String(20), nullable=False)
    HocKy = Column(String(50), nullable=False)
    SoTienPhaiNop = Column(Numeric(15, 2), nullable=False)
    TrangThai = Column(String(30), nullable=False) # 'CHUA_DONG', 'DA_DONG'

class GiaoDichModel(Base):
    __tablename__ = "GiaoDich"
    MaGiaoDich = Column(String(50), primary_key=True)
    MaNguoiDung = Column(Integer, nullable=False)
    MaHocPhi = Column(Integer, nullable=False)
    SoTienGiaoDich = Column(Numeric(15, 2), nullable=False)
    NgayGiaoDich = Column(DateTime, nullable=False)
    TrangThai = Column(String(30), nullable=False) # 'PENDING', 'SUCCESS'

class XacThucOTPModel(Base):
    __tablename__ = "XacThucOTP"
    MaOTP = Column(Integer, primary_key=True, index=True)
    MaGiaoDich = Column(String(50), nullable=False)
    MaCode = Column(String(10), nullable=False)
    ThoiGianTao = Column(DateTime, nullable=False)
    ThoiGianHetHan = Column(DateTime, nullable=False)
    TrangThai = Column(String(30), nullable=False) # 'CHUA_SU_DUNG', 'DA_SU_DUNG'

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    MaNguoiDung: int
    HoTen: str

class UserProfileResponse(BaseModel):
    full_name: str
    phone: str
    email: str
    available_balance: float

class TuitionResponse(BaseModel):
    MaHocPhi: int
    mssv: str
    student_name: str
    tuition_amount: float
    status: str

class InitiatePaymentRequest(BaseModel):
    MaNguoiDung: int
    MaHocPhi: int

class InitiatePaymentResponse(BaseModel):
    transaction_id: str
    message: str

class ConfirmPaymentRequest(BaseModel):
    MaGiaoDich: str
    otp: str

class TransactionResponse(BaseModel):
    message: str
    transaction_id: str
    status: str


# --- API ENDPOINTS ---

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Authentication"])
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    1. Đăng nhập hệ thống dựa trên cơ sở dữ liệu PostgreSQL
    """
    user = db.query(UserModel).filter(
        UserModel.TenDangNhap == request.username,
        UserModel.MatKhau == request.password
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )
    
    return {
        "access_token": f"mock_jwt_token_{user.MaNguoiDung}",
        "token_type": "bearer",
        "MaNguoiDung": user.MaNguoiDung,
        "HoTen": user.HoTen
    }

@app.get("/api/v1/users/me", response_model=UserProfileResponse, tags=["User"])
async def get_my_profile(db: Session = Depends(get_db)):
    """
    2. Lấy thông tin tài khoản đang đăng nhập
    """
    # Lấy user mặc định đầu tiên (phuc123) để demo giao diện
    user = db.query(UserModel).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    return {
        "full_name": user.HoTen,
        "phone": "0901234567",
        "email": user.Email,
        "available_balance": float(user.SoDuKhaDung)
    }

@app.get("/api/v1/students/{mssv}/tuition", response_model=TuitionResponse, tags=["Tuition"])
async def lookup_tuition(
    mssv: str = Path(..., title="Mã số sinh viên", min_length=5),
    db: Session = Depends(get_db)
):
    """
    3. Tra cứu thông tin học phí từ database
    """
    sv = db.query(SinhVienModel).filter(SinhVienModel.MSSV == mssv).first()
    hp = db.query(HocPhiModel).filter(HocPhiModel.MSSV == mssv, HocPhiModel.TrangThai == 'CHUA_DONG').first()
    
    if not sv or not hp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông tin sinh viên hoặc học phí đã được thanh toán"
        )
    
    return {
        "MaHocPhi": hp.MaHocPhi,
        "mssv": sv.MSSV,
        "student_name": sv.HoTen,
        "tuition_amount": float(hp.SoTienPhaiNop),
        "status": hp.TrangThai
    }

@app.post("/api/v1/payments/initiate", response_model=InitiatePaymentResponse, status_code=status.HTTP_201_CREATED, tags=["Payment"])
async def initiate_payment(
    request: InitiatePaymentRequest,
    db: Session = Depends(get_db)
):
    """
    4. Khởi tạo giao dịch, kiểm tra số dư và sinh OTP (thời hạn 5 phút)
    """
    user = db.query(UserModel).filter(UserModel.MaNguoiDung == request.MaNguoiDung).first()
    hp = db.query(HocPhiModel).filter(HocPhiModel.MaHocPhi == request.MaHocPhi).first()
    
    if not user or not hp:
        raise HTTPException(status_code=400, detail="Dữ liệu giao dịch không hợp lệ")
        
    if float(user.SoDuKhaDung) < float(hp.SoTienPhaiNop):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số dư khả dụng không đủ để thực hiện giao dịch"
        )

    # Tạo mã giao dịch và bản ghi PENDING
    ma_giao_dich = f"TXN_{int(datetime.utcnow().timestamp())}"
    
    gd = GiaoDichModel(
        MaGiaoDich=ma_giao_dich,
        MaNguoiDung=user.MaNguoiDung,
        MaHocPhi=hp.MaHocPhi,
        SoTienGiaoDich=hp.SoTienPhaiNop,
        NgayGiaoDich=datetime.utcnow(),
        TrangThai="PENDING"
    )
    db.add(gd)

    # Sinh OTP ngẫu nhiên 6 số, hiệu lực 5 phút[cite: 3]
    ma_code = "123456" # Cố định 123456 để dễ test demo, hoặc dùng random.randint(100000, 999999)
    otp = XacThucOTPModel(
        MaGiaoDich=ma_giao_dich,
        MaCode=ma_code,
        ThoiGianTao=datetime.utcnow(),
        ThoiGianHetHan=datetime.utcnow() + timedelta(minutes=5),
        TrangThai="CHUA_SU_DUNG"
    )
    db.add(otp)
    db.commit()

    print(f"[EMAIL SIMULATION] Gửi OTP {ma_code} đến email {user.Email}")

    return {
        "transaction_id": ma_giao_dich,
        "message": "OTP đã được gửi đến email của bạn."
    }

@app.post("/api/v1/payments/confirm", response_model=TransactionResponse, tags=["Payment"])
async def confirm_payment(
    request: ConfirmPaymentRequest,
    db: Session = Depends(get_db)
):
    """
    5. Xác nhận OTP, trừ tiền tài khoản, gạch nợ học phí và lưu lịch sử[cite: 3]
    """
    otp = db.query(XacThucOTPModel).filter(
        XacThucOTPModel.MaGiaoDich == request.MaGiaoDich,
        XacThucOTPModel.MaCode == request.otp,
        XacThucOTPModel.TrangThai == "CHUA_SU_DUNG"
    ).first()

    if not otp or datetime.utcnow() > otp.ThoiGianHetHan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn"
        )

    # Vô hiệu hóa OTP ngay lập tức sau 1 lần dùng[cite: 3]
    otp.TrangThai = "DA_SU_DUNG"

    gd = db.query(GiaoDichModel).filter(GiaoDichModel.MaGiaoDich == request.MaGiaoDich).first()
    gd.TrangThai = "SUCCESS"

    # Trừ tiền người dùng và gạch nợ học phí
    user = db.query(UserModel).filter(UserModel.MaNguoiDung == gd.MaNguoiDung).first()
    hp = db.query(HocPhiModel).filter(HocPhiModel.MaHocPhi == gd.MaHocPhi).first()

    user.SoDuKhaDung = float(user.SoDuKhaDung) - float(gd.SoTienGiaoDich)
    hp.TrangThai = "DA_DONG"

    db.commit()

    return {
        "message": "Thanh toán học phí thành công",
        "transaction_id": request.MaGiaoDich,
        "status": "SUCCESS"
    }