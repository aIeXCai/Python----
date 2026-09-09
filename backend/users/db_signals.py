"""每个 SQLite 连接建立时的 PRAGMA 配置（WAL + busy_timeout）。

SQLite 同一时刻只允许一个写事务；默认事务日志 (rollback journal) 下，
读者也会阻塞写者，课堂上全班并发作答很容易抛 "database is locked"。
改用 WAL（Write-Ahead Logging）后：读者不阻塞写者、写操作仍串行但等待
窗口大幅减小；synchronous=NORMAL 在 WAL 下兼顾可靠性与吞吐。

注意：连接级 pragma（synchronous/busy_timeout）每次新建连接都要设置，
因此通过 django.db.backends.signals.connection_created 统一处理。
"""

from django.db.backends.signals import connection_created


def _apply_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != 'sqlite':
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.fetchall()
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.fetchall()
        # 与 settings 中 OPTIONS['timeout']=30 保持一致（双保险）
        cursor.execute('PRAGMA busy_timeout=30000;')
        cursor.fetchall()


def connect_sqlite_pragmas():
    # weak=False：避免接收器被垃圾回收导致 pragma 不再应用
    connection_created.connect(_apply_sqlite_pragmas, weak=False)
