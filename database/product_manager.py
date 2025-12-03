# database/product_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Dict, List, Optional, Tuple
import logging

from database.models import Product

logger = logging.getLogger(__name__)


class ProductManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_product(
            self,
            seller_account_id: int,
            supplier_article: str
    ) -> Product:
        """
        Находим существующий продукт или создаем новый
        """
        # Ищем существующий продукт
        stmt = select(Product).where(
            and_(
                Product.seller_account_id == seller_account_id,
                Product.supplier_article == supplier_article
            )
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()

        if product:
            logger.debug(f"Товар найден: {supplier_article}")
            return product

        # Создаем новый продукт
        logger.info(f"Создаем новый товар: {supplier_article} для аккаунта {seller_account_id}")
        product = Product(
            seller_account_id=seller_account_id,
            supplier_article=supplier_article,
            custom_name=None  # Название можно установить позже
        )

        self.session.add(product)
        try:
            await self.session.commit()
            logger.info(f"Товар создан: {supplier_article}")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при создании товара {supplier_article}: {e}")
            raise

        return product

    async def get_custom_names_dict(self, seller_account_id: int) -> Dict[str, str]:
        """
        Получаем словарь: {supplier_article: custom_name или supplier_article}
        """
        stmt = select(Product.supplier_article, Product.custom_name).where(
            Product.seller_account_id == seller_account_id
        )
        result = await self.session.execute(stmt)

        names_dict = {}
        for article, custom_name in result:
            # Используем кастомное название если есть, иначе сам артикул
            names_dict[article] = custom_name if custom_name else article

        return names_dict

    async def update_custom_name(
            self,
            seller_account_id: int,
            supplier_article: str,
            custom_name: str
    ) -> bool:
        """
        Обновляем кастомное название товара
        """
        stmt = select(Product).where(
            and_(
                Product.seller_account_id == seller_account_id,
                Product.supplier_article == supplier_article
            )
        )
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            logger.warning(f"Товар не найден: {supplier_article}")
            return False

        product.custom_name = custom_name
        try:
            await self.session.commit()
            logger.info(f"Название обновлено для {supplier_article}: {custom_name}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при обновлении названия: {e}")
            return False

    async def get_all_products(self, seller_account_id: int) -> List[Product]:
        """
        Получаем все товары аккаунта
        """
        stmt = select(Product).where(
            Product.seller_account_id == seller_account_id
        ).order_by(Product.supplier_article)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
