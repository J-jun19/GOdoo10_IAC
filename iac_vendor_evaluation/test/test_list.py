# -*- coding: utf-8 -*-

import erppeek
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import re
from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
from datetime import datetime, timedelta

import base64
import urllib
import urllib2
import xlrd


if __name__ == "__main__":
    list_data = [[2659, '2018-08-08', 186],
                 [3733, '2019-03-06', 820],
                 [3733, '2019-05-06', 910],
                 [1165, '2019-05-06', 923],
                 [478, '2019-05-06', 933],

    ]
    for supplier_company_id,score_snapshot,class_company_id in list_data:
        print(supplier_company_id)
        print(score_snapshot)
        print(class_company_id)
