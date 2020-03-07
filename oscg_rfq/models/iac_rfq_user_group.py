# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
import  traceback
import threading


class IacRfqUserGroup(models.Model):
    _name = "iac.rfq.user.group"

    plant_id = fields.Many2one('pur.org.data','Plant Info')
    user_id = fields.Many2one('res.users','User Info')
    group_id = fields.Many2one('res.groups','Group Info')
    division_id=fields.Many2one('division.code','Division Info')
    plant_code=fields.Char('Plant Code')
    user_code=fields.Char('User Code')
    division_code=fields.Char('Division Code')
    memo = fields.Text("Memo Info")

    @api.model
    def check_rfq_create_access(self):
        """
        校验当前登录账户是否有权限进行rfq create 操作,
        1   返回布尔值 ,有权操作返回真,无权操作返回假
        2   返回适用的规则id
        :return:
        """

        division_id_list=[]
        plant_id_list=[]
        group_id_list=[]
        user_id=self.env.user.id
        plant_id_list=self.env.user.plant_id_list
        division_id_list=self.env.user.plant_id_list
        group_id_list=[g.id for g in self.env.user.groups_id]

        #获取全部列表
        rule_list=self.search([])

        #遍历所有条件,满足其中之一就退出返回true
        for rule in rule_list:
            #判断操作员条件
            if rule.user_id.exists():
                if user_id !=rule.user_id.id:
                    continue
            #判断组条件
            if rule.group_id.exists():
                if  rule.group_id.id not in group_id_list:
                    continue
            #判断厂别条件
            if rule.plant_id.exists():
                if  rule.plant_id.id not in plant_id_list:
                    continue
            #判断division条件
            if rule.division_id.exists():
                if  rule.division_id.id not in division_id_list:
                    continue
            #所有条件都满足的情况下,返回真和 当前规则id
            return True,rule.id
        return False,0
