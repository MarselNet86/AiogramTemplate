from os import getenv
from dotenv import load_dotenv
from typing import Final


load_dotenv()


class TgKeys:
    TOKEN: Final = getenv.get('TOKEN', 'define me!')
