# -*- coding: utf-8 -*-

import json
import xlwt
import time,base64
import datetime
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from xlrd import open_workbook
from odoo import models, fields, api
import psycopg2
import logging
from dateutil.relativedelta import relativedelta
from StringIO import StringIO
import pdb
import odoo
import threading
import traceback
_logger = logging.getLogger(__name__)


def printdebug(func):
    def __decorator(user):    #add parameter receive the user information
        print('enter the login')
        func(user)  #pass user to login
        print('exit the login')
    return __decorator

@printdebug
def login(user):
    print('in login:' + user)


if __name__ == "__main__":
    login("lwt")
    pass