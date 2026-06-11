import os
import sys
import logging
from rt_thread_club import login_in_club


def init_logger():
    log_format = " %(filename)s %(lineno)d <ignore> %(levelname)s %(message)s "
    date_format = '%Y-%m-%d  %H:%M:%S %a '
    logging.basicConfig(level=logging.INFO,
                        format=log_format,
                        datefmt=date_format
                        )


def main():
    username = os.environ["CLUB_USERNAME"]
    password = os.environ["CLUB_PASSWORD"]

    day_num = login_in_club(username, password)
    try:
        with open("sign_in_days.txt", "w") as f:
            f.write(str(day_num) if day_num else "已签到")
    except Exception as e:
        logging.error(e)
        sys.exit(1)


if __name__ == "__main__":
    init_logger()
    main()
