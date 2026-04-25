from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str
    tipo_usuario: str