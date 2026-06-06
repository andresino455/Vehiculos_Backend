#!/bin/bash

echo "==> Instalando dependencias..."
pip install -r requirements.txt

echo "==> Creando tenant principal..."
python << 'EOF'
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Verificar si ya existe el tenant principal
    resultado = conn.execute(text("""
        SELECT id FROM tenants 
        WHERE id = '00000000-0000-0000-0000-000000000001'
    """)).fetchone()
    
    if not resultado:
        conn.execute(text("""
            INSERT INTO tenants (id, nombre, descripcion, activo)
            VALUES (
                '00000000-0000-0000-0000-000000000001',
                'Red Principal',
                'Tenant principal del sistema',
                true
            )
        """))
        conn.commit()
        print("[SEED] Tenant principal creado correctamente")
    else:
        print("[SEED] Tenant principal ya existe, omitiendo...")

EOF

echo "==> Build completado"