"""PNG 로더. ``ext.png`` 가 ``pillow`` 일 때 쓰인다.

실제 로직은 :class:`loader.image_loader.PillowImageLoader` 공통 베이스에 있다.
"""

from loader.image_loader import PillowImageLoader


class Loader(PillowImageLoader):
    pass
