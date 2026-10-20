from app.extensions import db
from app.models import Business, Product
from sqlalchemy import func


class ProductService:
    @staticmethod
    def format_catalog(products) -> str:
        if not products:
            return "No active products are configured."
        rows = []
        for product in products:
            aliases = f" (aliases: {product.aliases})" if product.aliases else ""
            rows.append(f"- {product.canonical_name}{aliases}: ${product.price:,.0f} COP")
        return "\n".join(rows)

    @staticmethod
    def get_or_create_business(phone_number: str) -> Business:
        business = Business.query.filter_by(phone_number=phone_number).first()
        if business:
            return business

        business = Business(name=phone_number, phone_number=phone_number)
        db.session.add(business)
        db.session.commit()
        return business

    @staticmethod
    def list_products(business_id: int):
        return Product.query.filter_by(business_id=business_id).order_by(Product.id).all()

    @staticmethod
    def list_active_products(business_id: int):
        return Product.query.filter_by(business_id=business_id, is_active=True).order_by(Product.id).all()

    @staticmethod
    def find_product(business_id: int, canonical_name: str):
        return Product.query.filter(
            Product.business_id == business_id,
            func.lower(Product.canonical_name) == canonical_name.strip().lower(),
        ).first()

    @staticmethod
    def upsert_catalog_product(business_id: int, canonical_name: str, price: float, alias: str):
        product = ProductService.find_product(business_id, canonical_name)
        if product is None:
            product = Product(
                business_id=business_id,
                name=canonical_name,
                canonical_name=canonical_name,
                aliases=alias or None,
                price=price,
                is_active=True,
            )
            db.session.add(product)
            db.session.commit()
            return product, "created"

        action = "unchanged"
        if product.price != price:
            product.price = price
            action = "updated"
        if alias and alias.casefold() not in (product.aliases or "").casefold():
            product.aliases = "; ".join(filter(None, [product.aliases, alias]))
        if action != "unchanged" or alias:
            db.session.commit()
        return product, action

    @staticmethod
    def create_product(business_id: int, name: str, price: float, aliases: str = "") -> Product:
        product = Product(
            business_id=business_id,
            name=name,
            canonical_name=name,
            aliases=aliases or None,
            price=price,
            is_active=True,
        )
        db.session.add(product)
        db.session.commit()
        return product

    @staticmethod
    def update_product(business_id: int, product_id: int, name=None, price=None, aliases=None):
        product = Product.query.filter_by(id=product_id, business_id=business_id).first()
        if product is None:
            return None
        if name is not None:
            product.name = name
            product.canonical_name = name
        if price is not None:
            product.price = price
        if aliases is not None:
            product.aliases = aliases or None
        db.session.commit()
        return product

    @staticmethod
    def delete_product(business_id: int, product_id: int) -> bool:
        product = Product.query.filter_by(id=product_id, business_id=business_id).first()
        if product is None:
            return False
        db.session.delete(product)
        db.session.commit()
        return True
