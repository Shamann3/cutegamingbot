"""Общая настройка прогона tests/.

Тесты импортируют продакшен-код по абсолютным путям (``bot.funcs...``), поэтому
корень репозитория должен лежать в sys.path независимо от того, из какой папки
запущен pytest.

Здесь сознательно НЕ подменяется sys.stdout: pytest отдаёт тестам временный файл
захвата вывода, и любая замена (``sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
...)``) закрывает его, из-за чего весь прогон падал с
``ValueError: I/O operation on closed file``. Кодировку консоли отдельные файлы
настраивают сами, но только при запуске как скрипт (``if __name__ == "__main__"``)
и через ``reconfigure``, который исходный поток не закрывает.
"""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
