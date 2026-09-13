"""
Exportador completo da estrutura de um banco PostgreSQL/Supabase.

Funcionalidades:
- Lista schemas, tabelas e views
- Extrai colunas com tipos, nulabilidade, defaults e posições
- Identifica chaves primárias
- Identifica chaves estrangeiras com tabela/coluna referenciada
- Extrai índices com mapeamento real por coluna via pg_catalog
- Extrai constraints
- Exporta CSV consolidado
- Exporta JSON hierárquico por schema/tabela
- Usa variáveis de ambiente via .env

Requisitos:
    pip install psycopg2-binary python-dotenv

Exemplo de .env:
    SUPABASE_DB_HOST=your-project.supabase.co
    SUPABASE_DB_PORT=5432
    SUPABASE_DB_NAME=postgres
    SUPABASE_DB_USER=postgres
    SUPABASE_DB_PASSWORD=your_password
    SUPABASE_DB_SSLMODE=require
    SUPABASE_OUTPUT_DIR=output
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Coluna:
    schema: str
    tabela: str
    nome: str
    posicao: int
    tipo: str
    udt_name: str
    nullable: bool
    default: Optional[str]
    max_length: Optional[int]
    precision: Optional[int]
    scale: Optional[int]
    is_primary_key: bool = False
    foreign_key: Optional[Dict[str, Any]] = None
    indices: List[Dict[str, Any]] = field(default_factory=list)


class ExportadorEstruturaBD:

    def validar_variaveis_ambiente(self):
        variaveis = [
            "SUPABASE_DB_HOST",
            "SUPABASE_DB_PORT",
            "SUPABASE_DB_NAME",
            "SUPABASE_DB_USER",
            "SUPABASE_DB_PASSWORD",
        ]

        faltando = [v for v in variaveis if not os.getenv(v)]
        if faltando:
            raise RuntimeError(f"Variáveis ausentes no .env: {', '.join(faltando)}")


    def __init__(self) -> None:
        self.conn = None
        self.output_dir = Path(os.getenv("SUPABASE_OUTPUT_DIR", "output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def conectar(self) -> None:
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("SUPABASE_DB_HOST"),
                port=os.getenv("SUPABASE_DB_PORT", "5432"),
                dbname=os.getenv("SUPABASE_DB_NAME"),
                user=os.getenv("SUPABASE_DB_USER"),
                password=os.getenv("SUPABASE_DB_PASSWORD"),
                sslmode=os.getenv("SUPABASE_DB_SSLMODE", "require"),
            )
            logger.info("Conexão com o banco estabelecida com sucesso.")
        except Exception as e:
            logger.exception("Falha ao conectar ao banco.")
            raise RuntimeError(f"Erro ao conectar ao banco: {e}") from e

    def fechar(self) -> None:
        if self.conn:
            self.conn.close()
            logger.info("Conexão encerrada.")

    def _fetchall(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return list(cur.fetchall())

    def coletar_tabelas(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
        """
        return self._fetchall(query)

    def coletar_colunas(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            table_schema,
            table_name,
            ordinal_position,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position;
        """
        return self._fetchall(query)

    def coletar_pk(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
        ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position;
        """
        return self._fetchall(query)

    def coletar_fk(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position;
        """
        return self._fetchall(query)

    def coletar_constraints(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            table_schema,
            table_name,
            constraint_name,
            constraint_type
        FROM information_schema.table_constraints
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, constraint_type, constraint_name;
        """
        return self._fetchall(query)

    def coletar_views(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            table_schema,
            table_name,
            view_definition
        FROM information_schema.views
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
        """
        return self._fetchall(query)

    def coletar_indices(self) -> List[Dict[str, Any]]:
        query = """
        SELECT
            n.nspname AS schema_name,
            t.relname AS table_name,
            i.relname AS index_name,
            ix.indisunique AS is_unique,
            ix.indisprimary AS is_primary,
            pg_get_indexdef(ix.indexrelid) AS index_definition,
            ARRAY(
                SELECT a.attname
                FROM unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord)
                JOIN pg_attribute a
                  ON a.attrelid = t.oid
                 AND a.attnum = k.attnum
                ORDER BY k.ord
            ) AS index_columns
        FROM pg_class t
        JOIN pg_namespace n
          ON n.oid = t.relnamespace
        JOIN pg_index ix
          ON ix.indrelid = t.oid
        JOIN pg_class i
          ON i.oid = ix.indexrelid
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND t.relkind IN ('r', 'p')
        ORDER BY n.nspname, t.relname, i.relname;
        """
        return self._fetchall(query)

    def montar_mapas(self) -> Dict[str, Any]:
        tabelas = self.coletar_tabelas()
        colunas = self.coletar_colunas()
        pks = self.coletar_pk()
        fks = self.coletar_fk()
        constraints = self.coletar_constraints()
        views = self.coletar_views()
        indices = self.coletar_indices()

        pk_set = {
            (x["table_schema"], x["table_name"], x["column_name"])
            for x in pks
        }

        fk_map = {}
        for x in fks:
            fk_map[(x["table_schema"], x["table_name"], x["column_name"])] = x

        idx_map = {}
        for x in indices:
            for col in x["index_columns"] or []:
                chave = (x["schema_name"], x["table_name"], col)
                idx_map.setdefault(chave, []).append({
                    "index_name": x["index_name"],
                    "is_unique": x["is_unique"],
                    "is_primary": x["is_primary"],
                    "index_definition": x["index_definition"]
                })

        hierarquia: Dict[str, Dict[str, Any]] = {}

        for tabela in tabelas:
            schema = tabela["table_schema"]
            nome_tabela = tabela["table_name"]

            hierarquia.setdefault(schema, {})
            hierarquia[schema].setdefault(nome_tabela, {
                "table_type": tabela["table_type"],
                "columns": [],
                "primary_keys": [],
                "foreign_keys": [],
                "constraints": [],
                "indices": [],
                "views": []
            })

        for view in views:
            schema = view["table_schema"]
            nome_view = view["table_name"]
            hierarquia.setdefault(schema, {})
            if nome_view not in hierarquia[schema]:
                hierarquia[schema][nome_view] = {
                    "table_type": "VIEW",
                    "columns": [],
                    "primary_keys": [],
                    "foreign_keys": [],
                    "constraints": [],
                    "indices": [],
                    "views": []
                }
            hierarquia[schema][nome_view]["views"].append({
                "view_definition": view["view_definition"]
            })

        for col in colunas:
            schema = col["table_schema"]
            tabela = col["table_name"]
            chave_coluna = (schema, tabela, col["column_name"])

            coluna = {
                "name": col["column_name"],
                "position": col["ordinal_position"],
                "type": col["data_type"],
                "udt_name": col["udt_name"],
                "nullable": col["is_nullable"] == "YES",
                "default": col["column_default"],
                "character_maximum_length": col["character_maximum_length"],
                "numeric_precision": col["numeric_precision"],
                "numeric_scale": col["numeric_scale"],
                "is_primary_key": chave_coluna in pk_set,
                "foreign_key": fk_map.get(chave_coluna),
                "indices": idx_map.get(chave_coluna, [])
            }

            if schema not in hierarquia:
                hierarquia[schema] = {}
            if tabela not in hierarquia[schema]:
                hierarquia[schema][tabela] = {
                    "table_type": "BASE TABLE",
                    "columns": [],
                    "primary_keys": [],
                    "foreign_keys": [],
                    "constraints": [],
                    "indices": [],
                    "views": []
                }

            hierarquia[schema][tabela]["columns"].append(coluna)

            if coluna["is_primary_key"]:
                hierarquia[schema][tabela]["primary_keys"].append(col["column_name"])

            if coluna["foreign_key"]:
                hierarquia[schema][tabela]["foreign_keys"].append(coluna["foreign_key"])

            if coluna["indices"]:
                for idx in coluna["indices"]:
                    hierarquia[schema][tabela]["indices"].append({
                        "column": col["column_name"],
                        **idx
                    })

        for c in constraints:
            schema = c["table_schema"]
            tabela = c["table_name"]
            if schema in hierarquia and tabela in hierarquia[schema]:
                hierarquia[schema][tabela]["constraints"].append(c)

        return {
            "tabelas": tabelas,
            "colunas": colunas,
            "primary_keys": pks,
            "foreign_keys": fks,
            "constraints": constraints,
            "views": views,
            "indices": indices,
            "hierarquia": hierarquia,
        }

    def exportar_csv_consolidado(self, colunas: List[Dict[str, Any]], pks: List[Dict[str, Any]], fks: List[Dict[str, Any]], indices: List[Dict[str, Any]]) -> Path:
        pk_set = {(x["table_schema"], x["table_name"], x["column_name"]) for x in pks}
        fk_map = {(x["table_schema"], x["table_name"], x["column_name"]): x for x in fks}

        idx_map = {}
        for x in indices:
            for col in x["index_columns"] or []:
                idx_map.setdefault((x["schema_name"], x["table_name"], col), []).append(x)

        arquivo = self.output_dir / "estrutura_bd.csv"

        with arquivo.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "schema",
                    "tabela",
                    "coluna",
                    "posicao",
                    "tipo",
                    "udt_name",
                    "nullable",
                    "default",
                    "character_maximum_length",
                    "numeric_precision",
                    "numeric_scale",
                    "is_primary_key",
                    "foreign_table_schema",
                    "foreign_table_name",
                    "foreign_column_name",
                    "foreign_key_name",
                    "indices"
                ]
            )
            writer.writeheader()

            for col in colunas:
                chave = (col["table_schema"], col["table_name"], col["column_name"])
                fk = fk_map.get(chave)
                idxs = idx_map.get(chave, [])

                writer.writerow({
                    "schema": col["table_schema"],
                    "tabela": col["table_name"],
                    "coluna": col["column_name"],
                    "posicao": col["ordinal_position"],
                    "tipo": col["data_type"],
                    "udt_name": col["udt_name"],
                    "nullable": col["is_nullable"],
                    "default": col["column_default"],
                    "character_maximum_length": col["character_maximum_length"],
                    "numeric_precision": col["numeric_precision"],
                    "numeric_scale": col["numeric_scale"],
                    "is_primary_key": chave in pk_set,
                    "foreign_table_schema": fk["foreign_table_schema"] if fk else None,
                    "foreign_table_name": fk["foreign_table_name"] if fk else None,
                    "foreign_column_name": fk["foreign_column_name"] if fk else None,
                    "foreign_key_name": fk["constraint_name"] if fk else None,
                    "indices": json.dumps([
                        {
                            "index_name": i["index_name"],
                            "is_unique": i["is_unique"],
                            "is_primary": i["is_primary"]
                        }
                        for i in idxs
                    ], ensure_ascii=False)
                })

        logger.info("CSV exportado para %s", arquivo)
        return arquivo

    def exportar_json(self, hierarquia: Dict[str, Any]) -> Path:
        arquivo = self.output_dir / "estrutura_bd.json"
        with arquivo.open("w", encoding="utf-8") as f:
            json.dump(hierarquia, f, indent=2, ensure_ascii=False, default=str)
        logger.info("JSON exportado para %s", arquivo)
        return arquivo

    def executar(self) -> None:
        try:
            self.validar_variaveis_ambiente()
            self.conectar()
            dados = self.montar_mapas()

            self.exportar_csv_consolidado(
                colunas=dados["colunas"],
                pks=dados["primary_keys"],
                fks=dados["foreign_keys"],
                indices=dados["indices"]
            )
            self.exportar_json(dados["hierarquia"])

            logger.info("Exportação concluída com sucesso.")
        except Exception as e:
            logger.exception("Erro na exportação.")
            raise
        finally:
            self.fechar()


if __name__ == "__main__":
    ExportadorEstruturaBD().executar()