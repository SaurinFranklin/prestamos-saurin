"""Modelos ORM."""
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class PrestamoDB(Base):
    __tablename__ = "prestamos"

    id = Column(String, primary_key=True, index=True)
    deudor = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    interes = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    saldo = Column(Float, nullable=False)
    modalidad = Column(String, default="Diario")
    estado = Column(String, default="Puntual")
    cobrador_asignado = Column(String, nullable=False)

    pagos = relationship("PagoDB", back_populates="prestamo", cascade="all, delete-orphan")

    @property
    def completado(self) -> bool:
        return self.saldo <= 0

    @property
    def monto_interes(self) -> float:
        return self.monto * (self.interes / 100.0)


class PagoDB(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prestamo_id = Column(String, ForeignKey("prestamos.id"))
    fecha = Column(String, nullable=False)
    monto = Column(Float, nullable=False)
    registrado_por = Column(String, nullable=False)

    prestamo = relationship("PrestamoDB", back_populates="pagos")
