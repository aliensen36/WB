from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, BigInteger, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

# Пользователи
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False,
                                       index=True, comment='Telegram User ID')
    username: Mapped[str] = mapped_column(String(100), nullable=True, index=True,
                                          comment='Telegram username')
    first_name: Mapped[str] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str]  = mapped_column(String(150), nullable=True)


# Аккаунты магазинов
class SellerAccount(Base):
    __tablename__ = 'seller_accounts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=True)
    api_key: Mapped[str] = mapped_column(String(600), nullable=True, unique=True)

    # Связь с продуктами
    products: Mapped[list["Product"]] = relationship("Product",
                                                     back_populates="seller_account")

# Товары
class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Связь с аккаунтом продавца
    seller_account_id: Mapped[int] = mapped_column(ForeignKey('seller_accounts.id',
                                                              ondelete='CASCADE'),
                                                   nullable=False, index=True,
                                                   comment='Связь с аккаунтом продавца')
    supplier_article: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                                  comment='Артикул поставщика (ваш артикул)')
    # Название товара
    custom_name: Mapped[str] = mapped_column(String(255), nullable=True,
                                             comment='Кастомное название товара (для отчетов)')

    # Связи
    seller_account: Mapped["SellerAccount"] = relationship("SellerAccount",
                                                           back_populates="products")

    # Уникальная комбинация продавец + артикул
    __table_args__ = (Index('ix_unique_seller_supplier_article',
                           'seller_account_id',
                           'supplier_article', unique=True),)

