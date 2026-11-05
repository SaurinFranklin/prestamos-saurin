from datetime import date
from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class UsuarioDB(Base):
    """Representa a los usuarios del sistema (Administradores o Cobradores)."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(String, nullable=False, default="cobrador")
    nombre = Column(String, nullable=False)

    # Relación: Un cobrador/admin puede tener préstamos asignados o creados
    prestamos = relationship("PrestamoDB", back_populates="usuario")


class ClienteDB(Base):
    """Representa al deudor de forma independiente y persistente."""
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    documento_identidad = Column(String, unique=True, index=True, nullable=False)
    nombre_completo = Column(String, nullable=False, index=True)
    telefono = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    email = Column(String, nullable=True)
    calificacion = Column(String, default="Bueno")
    activo = Column(Boolean, default=True, nullable=False)

    # Relación: Un cliente puede tener múltiples préstamos históricos o activos
    prestamos = relationship("PrestamoDB", back_populates="cliente", cascade="all, delete-orphan")


class PrestamoDB(Base):
    """Representa el contrato de préstamo otorgado a un cliente."""
    __tablename__ = "prestamos"

    id = Column(String, primary_key=True, index=True)  # Ej: "PRES-101"
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    deudor = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    interes = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    saldo = Column(Float, nullable=False)
    modalidad = Column(String, default="Diario") 
    numero_cuotas = Column(Integer, default=1, nullable=False)
    fecha_inicio = Column(String, nullable=True)
    fecha_vencimiento = Column(String, nullable=True)
    estado = Column(String, default="Puntual")
    cobrador_asignado = Column(String, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    telefono = Column(String, nullable=True)
    metodo_pago = Column(String, default="Efectivo")

    # Relaciones ORM
    cliente = relationship("ClienteDB", back_populates="prestamos")
    usuario = relationship("UsuarioDB", back_populates="prestamos")
    cuotas = relationship("CuotaDB", back_populates="prestamo", cascade="all, delete-orphan", order_by="CuotaDB.numero_cuota")
    pagos = relationship("PagoDB", back_populates="prestamo", cascade="all, delete-orphan")

    @property
    def completado(self) -> bool:
        """Indica si el saldo ya fue cancelado en su totalidad."""
        return self.saldo <= 0

    @property
    def monto_interes(self) -> float:
        """Calcula el monto monetario que corresponde solo a la ganancia por interés."""
        return self.monto * (self.interes / 100.0)


class CuotaDB(Base):
    """Representa cada una de las cuotas del cronograma de amortización."""
    __tablename__ = "cuotas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prestamo_id = Column(String, ForeignKey("prestamos.id"), nullable=False, index=True)
    numero_cuota = Column(Integer, nullable=False)
    fecha_vencimiento = Column(String, nullable=False, index=True)
    monto_capital = Column(Float, nullable=False)
    monto_interes = Column(Float, nullable=False)
    total_cuota = Column(Float, nullable=False)
    saldo_cuota = Column(Float, nullable=False) 
    estado = Column(String, default="Pendiente", nullable=False)

    # Relaciones
    prestamo = relationship("PrestamoDB", back_populates="cuotas")
    pagos = relationship("PagoDB", back_populates="cuota")

    @property
    def pagada(self) -> bool:
        return self.saldo_cuota <= 0


class PagoDB(Base):
    """Representa cada transacción de cobro realizada."""
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prestamo_id = Column(String, ForeignKey("prestamos.id"), nullable=False, index=True)
    cuota_id = Column(Integer, ForeignKey("cuotas.id"), nullable=True)
    fecha = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    registrado_por = Column(String, nullable=False)
    metodo_pago = Column(String, default="Efectivo")
    notas = Column(String, nullable=True)

    # Relaciones
    prestamo = relationship("PrestamoDB", back_populates="pagos")
    cuota = relationship("CuotaDB", back_populates="pagos")