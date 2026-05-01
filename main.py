#!/usr/bin/env python3
"""超星学习通签到工具

用法:
    python main.py              命令行交互签到
    python main.py -server      Web 服务模式
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-server", "--server", "-s", "server"):
        import logging
        import uvicorn
        from chaoxing_sign.server import app

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        print("启动 Web 服务 → http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        from chaoxing_sign.cli.app import main
        main()
