# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api,odoo_env
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from odoo.odoo_env import odoo_env
from functools import wraps
import  traceback
import threading
import logging
import base64
import psycopg2
import os.path
from odoo import SUPERUSER_ID
_logger = logging.getLogger(__name__)

class IacVendorScorePartCategory(models.Model):
    """
    临时存放任务
    """
    _inherit = 'iac.score.part_category'

    # @api.model
    # def job_update_score_data(self,part_score_ids=[]):
    #     """
    #     传入多个score_part_id 进行更新操作
    #     :return:
    #     """
    #     if len(part_score_ids)==0:
    #         return 0
    #     for part_score_id in part_score_ids:
    #         part_score_rec = self.env["iac.score.part_category"].browse(part_score_id)
    #         part_score_rec.update_class_part_category()
    #     return 1
