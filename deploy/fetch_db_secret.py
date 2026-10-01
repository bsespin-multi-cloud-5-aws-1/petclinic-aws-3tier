#!/usr/bin/env python3

import json
import os
import pathlib
import subprocess
import tempfile

region = os.environ["AWS_REGION"]
secret_id = os.environ["PETCLINIC_SECRET_ID"]
db_host = os.environ["PETCLINIC_DB_HOST"]
db_replica_host = os.environ["PETCLINIC_DB_REPLICA_HOST"]
db_port = os.environ.get("PETCLINIC_DB_PORT", "3306")
db_name = os.environ.get("PETCLINIC_DB_NAME", "petclinic")

secret_string = subprocess.check_output(
    [
        "/usr/bin/aws",
        "secretsmanager",
        "get-secret-value",
        "--region", region,
        "--secret-id", secret_id,
        "--query", "SecretString",
        "--output", "text"
    ],
    text=True
).strip()

secret = json.loads(secret_string)

username = secret["username"]
password = secret["password"]

def escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )

content = "\n".join([
    "db.script=mysql",
    "jpa.database=MYSQL",
    "jpa.showSql=false",
    "jdbc.driverClassName=com.mysql.cj.jdbc.Driver",
    f"jdbc.url=jdbc:mysql://{escape(db_host)}:{escape(db_port)}/{escape(db_name)}?useUnicode=true",
    f"jdbc.read.url=jdbc:mysql://{escape(db_replica_host)}:{escape(db_port)}/{escape(db_name)}?useUnicode=true",
    f"jdbc.username={escape(username)}",
    f"jdbc.password={escape(password)}",
    "jdbc.initLocation=classpath:db/mysql/schema.sql",
    "jdbc.dataLocation=classpath:db/mysql/data.sql",
    ""
])

target_dir = pathlib.Path("/run/petclinic")
target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

fd, temporary_path = tempfile.mkstemp(
    prefix=".data-access.",
    dir=str(target_dir),
    text=True
)

try:
    os.fchmod(fd, 0o600)

    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(content)

    os.replace(
        temporary_path,
        target_dir / "data-access.properties"
    )
finally:
    if os.path.exists(temporary_path):
        os.unlink(temporary_path)
