from dataclasses import dataclass
from typing import Optional


@dataclass
class ProductResult:
    platform: str
    name: str
    brand: Optional[str]
    quantity: Optional[str]
    price: Optional[float]
    mrp: Optional[float]
    in_stock: bool = True

    @property
    def discount_percent(self) -> Optional[float]:
        if self.price is None or self.mrp in (None, 0):
            return None
        return round((1 - self.price / self.mrp) * 100, 1)
