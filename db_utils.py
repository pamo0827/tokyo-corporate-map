import mysql.connector
from contextlib import contextmanager
from config import db_config

def get_db_connection():
    """MySQLデータベースへの接続を取得する"""
    try:
        conn = mysql.connector.connect(
            host=db_config.host,
            user=db_config.user,
            password=db_config.password,
            database=db_config.database
        )
        return conn
    except mysql.connector.Error as err:
        print(f"MySQL connection error: {err}")
        return None

@contextmanager
def get_db_cursor():
    """データベース接続とカーソルのコンテキストマネージャー"""
    conn = get_db_connection()
    if not conn:
        raise mysql.connector.Error("Failed to connect to database")
    
    try:
        cursor = conn.cursor(dictionary=True)
        yield cursor
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        raise err
    finally:
        cursor.close()
        conn.close()

def create_database_and_tables():
    """データベースとテーブルを作成する"""
    try:
        conn = mysql.connector.connect(
            host=db_config.host,
            user=db_config.user,
            password=db_config.password
        )
        
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config.database} DEFAULT CHARACTER SET utf8mb4")
            cursor.execute(f"USE {db_config.database}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    address VARCHAR(255) NOT NULL,
                    latitude FLOAT,
                    longitude FLOAT,
                    corporate_number VARCHAR(20) UNIQUE
                )
            """)
        conn.commit()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Failed to create database or tables: {err}")
        if conn:
            conn.close()