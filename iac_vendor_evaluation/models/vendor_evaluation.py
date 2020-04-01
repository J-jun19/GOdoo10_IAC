# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
import logging
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from datetime import datetime, timedelta
import traceback
import threading
from odoo import tools
# from task import TaskVendorScore
# import sys
# sys.path.append("D:/GOdoo10_IAC/myaddons/iac_vendor_evaluation")
from odoo.odoo_env import odoo_env

_logger = logging.getLogger(__name__)

class IacScoreList(models.Model):
    """
    supplier company评核名单表 Vscore_Gen_List
    由job自动产生
    """
    _name = 'iac.score.list'
    _description = "Vendor Score List"
    _order = "id desc"

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    plant_id = fields.Many2one('pur.org.data', string="Plant")
    vendor_ids = fields.Many2many('iac.vendor', string="Vendor")
    vendor_codes = fields.Char(string="Vendor Codes", compute='_taken_vendor_codes')# SC 中参与评核的Vendor Code，多个Vendor Code用逗号隔开
    score_plant_id = fields.Many2one('iac.score.plant', string="Score Plant")
    state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)  # 识别快照号，标记使用的哪个材料类别/评分区间/失败成本区间的快照
    score_type=fields.Selection([('job','Job'),('manual','Manual')],string="Score Type",default="job")#标识评核名单的类别，是job生成的，还是手动产生的

    @api.depends('vendor_ids')
    def _taken_vendor_codes(self):
        for v in self:
            vendor_codes = []
            for vendor_id in v.vendor_ids:
                vendor_codes.append(vendor_id.vendor_code)
            v.vendor_codes = ','.join(vendor_codes)

class IacScoreSupplierCompany(models.Model):
    """
    Supplier Company分厂区分数表 vs_gen_scclass
    二级评分信息表
    Supplier Company+part_category_ids
    """
    _name = 'iac.score.supplier_company'
    _description = "Supplier Company Score"
    _order = "id desc"

    score_list_id = fields.Many2one('iac.score.list', string="Score List")  # 评核名单
    class_supplier_company_id = fields.Many2one('iac.class.supplier_company', string="Supplier Company Class")#SC评定信息
    score_part_category_ids = fields.One2many('iac.score.part_category', 'score_supplier_company_id', string="Part Category Score")# 材料类别评分表
    #supplier_company_id = fields.Many2one('iac.supplier.company', related="score_list_id.supplier_company_id", string="Supplier Company")
    #plant_id = fields.Many2one('pur.org.data', related="score_list_id.plant_id", string="Plant")
    plant_id = fields.Many2one('pur.org.data',  string="Plant")

    supplier_type = fields.Selection(related="supplier_company_id.supplier_type", string="Supplier Type")
    score_memo = fields.Text(string="Score Memo")
    scm_controller_id = fields.Many2one('res.partner', string="SCM Controller", domain="[('supplier','=',False)]")
    scm_memo = fields.Text(string="SCM Controller Memo")
    qm_controller_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    qm_leader_id = fields.Many2one('res.partner', string="QM Leader", domain="[('supplier','=',False)]")
    qm_memo = fields.Text(string="QM Leader Memo")
    state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    finish_date = fields.Datetime(string="Finish Date")
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)
    plant_score = fields.Float(string="Plant Score",  digits=(7, 2)) # plant的加权分数,需要通过user_score 联动
    business_amount = fields.Float(string="Business Amount", digits=(12, 2)) # plant交易金额
    weight = fields.Float(string="Weight", digits=(5, 2))  # 权重,当前厂的入料金额占所有厂的入料金额的比重
    weight_score = fields.Float(string="Weight Score",digits=(7, 2))  # 加权分数
    supplier_company_id = fields.Many2one('iac.supplier.company',  string="Supplier Company")
    gr_qty = fields.Float(string="GR Qty", digits=(12, 2)) # plant入料数量
    #plant_score = fields.Float(string="Plant Score", compute="_compute_plant_score", digits=(7, 2), store=True) # plant的加权分数
    #business_amount = fields.Float(string="Business Amount", compute="_compute_business_amount", digits=(12, 2), store=True) # plant交易金额
    #weight = fields.Float(string="Weight", compute="_compute_weight", digits=(5, 2))  # 权重
    #weight_score = fields.Float(string="Weight Score", compute="_compute_weight_score", digits=(7, 2), store=True)  # 加权分数



    @api.model
    def create(self,vals):
        result=super(IacScoreSupplierCompany,self).create(vals)


        #获取当前厂区的入料金额汇总
        self.env.cr.execute("""
            SELECT
                COALESCE(SUM (gr_amount),0) business_amount
            FROM
                iac_score_part_category
            WHERE
            score_snapshot=%s
            and supplier_company_id=%s
            and plant_id=%s
                        """,(result.score_snapshot,result.supplier_company_id.id,result.plant_id.id))
        pg_result = self.env.cr.dictfetchone()
        #获取分厂区的
        business_amount=pg_result["business_amount"]
        update_vals={
            "business_amount":business_amount
        }

        #更新weight数据
        super(IacScoreSupplierCompany,result).write(update_vals)

        #在job中完成不在需要
        #更新当前公司的所有厂区权重信息
        #self.env["iac.score.supplier_company"].update_weight(result.supplier_company_id,result.score_snapshot)
        return result

    # 不能注释
    @api.model
    def update_weight(self,supplier_company_id,score_snapshot):
        """
        更新指定公司的所有厂区的指定期间的权重数据
        :param supplier_company_id:
        :return:
        """

        #获取当前公司的入料金额汇总
        #获取跨厂区的入料金额汇总汇总数据,不分材料类别
        self.env.cr.execute("""
            SELECT
                COALESCE(SUM (gr_amount),0) business_amount_sum
            FROM
                iac_score_part_category
            WHERE
            score_snapshot=%s
            and supplier_company_id=%s
                        """,(score_snapshot,supplier_company_id,))
        pg_result = self.env.cr.dictfetchone()
        business_amount_sum=pg_result["business_amount_sum"]
        #入料总金额为0,不更新权重值
        if business_amount_sum==0.0:
            return

        #对公司中所有的厂区计算权重数值,在创建记录的时候已经得到了分厂区的入料数据,所以在此步骤计算各自的权重值即可
        domain=[
            ('supplier_company_id','=',supplier_company_id),
            ('score_snapshot','=',score_snapshot)
        ]
        score_company_list=self.env["iac.score.supplier_company"].search(domain)
        weight_sum=1.0
        for index,score_company in enumerate(score_company_list):
            #只有1个厂区的情况下
            if len(score_company_list.ids)==1:
                score_company.weight=1
                score_company._update_score_company_data()
                break

            #另外一种情况存在多个厂区的情况下
            #当前记录不是最后一个厂区
            if (index+1)<len(score_company_list.ids):
                cur_weight=score_company.business_amount/business_amount_sum
                score_company.weight=cur_weight
                score_company._update_score_company_data()
                weight_sum-=cur_weight
            else:
                #如果当前记录是最后一个厂区,那么剩余的权重就是最后一条记录的
                score_company.weight=weight_sum
                score_company._update_score_company_data()

    # 不能注释
    def _update_score_company_data(self):
        """
        只能被单一记录对象调用
        前提是只能在全部part_class_category 都评定的完成的情况下
        更新分数相关的数据
        """
        #从part.category中获取当前厂区的加权分数
        self.env.cr.execute("""
            SELECT
                COALESCE(SUM (gr_qty_weight*user_score),0) weight_score
            FROM
                iac_score_part_category
            WHERE
            score_snapshot=%s
            and supplier_company_id=%s
            and plant_id=%s
                        """,(self.score_snapshot,self.supplier_company_id.id,self.plant_id.id))
        pg_result = self.env.cr.dictfetchone()
        update_vals={
            "plant_score":pg_result["weight_score"],
            "weight_score":pg_result["weight_score"],
        }
        self.write(update_vals)

    # 不能注释
    @api.model
    def update_score_company_data_ref(self,supplier_company_id,score_snapshot,i,lenth):
        """
        更新指定 supplier_company的 score_supplier_company 数据,只有当前supplier_company的全部 class_part_category都
        评分完成的情况下才进行级联更新操作
        """
        #检查是否全部的class_part_category是否评定完成

        #更新分指定公司的,分厂区权重 和权重分数数据
        self.env["iac.score.supplier_company"].update_weight(supplier_company_id,score_snapshot)

        domain=[
                ('supplier_company_id','=',supplier_company_id),
                ('score_snapshot','=',score_snapshot),
                ('state','!=','done')
            ]
        class_part_category_list=self.env["iac.class.part_category"].search(domain,limit=1)
        if not class_part_category_list and i == lenth:
            domain_score_company=[
                ('supplier_company_id','=',supplier_company_id),
                ('score_snapshot','=',score_snapshot),
            ]
            score_company_list=self.env["iac.score.supplier_company"].search(domain_score_company)

            #级联更新class_supplier_company
            if score_company_list:
                score_company_list[0].class_supplier_company_id._update_class_supplier_company_data()



    # @api.multi
    # def _compute_weight(self):
    #     for score in self:
    #         sum_amount = 0
    #         # 各plant的交易金额汇总
    #         for sc_score in self.env['iac.score.supplier_company'].search([('supplier_company_id', '=', score.supplier_company_id.id),
    #                                       ('score_snapshot', '=', score.score_snapshot)]):
    #             sum_amount += sc_score.business_amount
    #
    #         if sum_amount > 0:
    #             score.weight = score.business_amount / sum_amount
    #         else:
    #             score.weight = 0

    # @api.depends('plant_score', 'weight')
    # def _compute_weight_score(self):
    #     for score in self:
    #         score.weight_score = score.plant_score * score.weight

    # @api.depends('score_part_category_ids.plant_id', 'score_part_category_ids.gr_amount')
    # def _compute_business_amount(self):
    #     for score in self:
    #         sum_amount = 0
    #         for score_part_category in score.score_part_category_ids:
    #             if score.plant_id == score_part_category.plant_id:
    #                 sum_amount += score_part_category.gr_amount
    #         score.business_amount = sum_amount

    # @api.depends('score_part_category_ids.plant_id', 'score_part_category_ids.weight_score')
    # def _compute_plant_score(self):
    #     for score in self:
    #         sum_score = 0
    #         for score_part_category_id in score.score_part_category_ids:
    #             if score.plant_id.id == score_part_category_id.plant_id.id:
    #                 sum_score += score_part_category_id.weight_score
    #         score.plant_score = sum_score

class IacScoreSupplierCompanyClass(models.Model):
    """
    Supplier Company分厂区分数表，配合class使用，不执行记录规则
    """
    _name = 'iac.class.score.supplier_company'
    _inherit = 'iac.score.supplier_company'
    _table = 'iac_score_supplier_company'

class IacScorePartCategory(models.Model):
    """
    Vendor材料类别分数表 vs_gen_partclass

    三级级评分信息表
    Supplier Company+part_category_id
    """
    _name = 'iac.score.part_category'
    _description = "Vendor Score Part Category Class"
    _order = "supplier_company_id,plant_id,part_category_id,id"

    score_list_id = fields.Many2one('iac.score.list', string="Score List")# 评核名单
    score_supplier_company_id = fields.Many2one('iac.score.supplier_company', string="Score List")  # 供应商评核
    class_part_category_id = fields.Many2one('iac.class.part_category', string="Current Part Class")
    #supplier_company_id = fields.Many2one('iac.supplier.company', related="score_supplier_company_id.supplier_company_id", string="Supplier Company")
    supplier_code = fields.Char(string="Supplier Code", related='supplier_company_id.company_no')
    supplier_name = fields.Char(string="Supplier Name", related='supplier_company_id.name')
    supplier_class = fields.Selection([('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('DW', 'DW')], related='supplier_company_id.current_class',string="Current SC Class")
    #plant_id = fields.Many2one('pur.org.data', related="score_supplier_company_id.plant_id", string="Plant")
    plant_id = fields.Many2one('pur.org.data',  string="Plant")
    part_class = fields.Many2one('iac.part.class', string='Part Class', related='part_category_id.part_class', help=u'材料大类')
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")# 材料类别
    #part_category_class = fields.Char(string="Part Category Class", compute='_compute_part_category_class')  # PC上一次评核的class
    part_category_class = fields.Char(string="Part Category Class")  # PC上一次评核的class
    line_ids = fields.One2many('iac.score.part_category.line', 'score_part_category_id', string=u"材料类别评分项")
    scm_controller_id = fields.Many2one('res.partner', string="SCM Controller", domain="[('supplier','=',False)]")
    scm_partner_id = fields.Many2one('res.partner', string="SCM User", domain="[('in_scm_user_group','=',True)]")
    qm_controller_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    qm_leader_id = fields.Many2one('res.partner', string="QM Leader", domain="[('supplier','=',False)]")
    qm_partner_id = fields.Many2one('res.partner', string="QM User", domain="[('in_qm_user_group','=',True)]")
    type_memo = fields.Text(string="Type Memo")
    gr_qty = fields.Float(string="GR Quantity", digits=(10, 3), readonly=True)# 入料批数
    gr_amount = fields.Float(string="GR Amount", digits=(10, 2), readonly=True)# 入料金额
    #weight = fields.Float(string="Weight", compute="_compute_weight", digits=(5, 2))# 权重
    #user_score = fields.Float(string="User Score", compute="_compute_user_score", digits=(7, 2), store=True)# line加总
    #scm_user_score = fields.Float(string="SCM Score", compute="_compute_scm_user_score", digits=(7, 2), store=True)# line加总
    #qm_user_score = fields.Float(string="QM Score", compute="_compute_qm_user_score", digits=(7, 2), store=True)  # line加总
    #weight_score = fields.Float(string="Weight Score", compute="_compute_weight_score", digits=(7, 2), store=True)# 加权分数
    weight = fields.Float(string="Weight",  digits=(5, 2))# 当前厂+当前材料类别的入料金额 占所有厂的+当前材料类别的入料金额比重
    gr_qty_weight = fields.Float(string="GR Qty Weight",  digits=(5, 2))# 当前厂+当前材料类别的入料数量 当前厂的所有材料类别的入料数量比重
    user_score = fields.Float(string="User Score",  digits=(7, 2), store=True)# line加总
    scm_user_score = fields.Float(string="SCM Score", digits=(7, 2), store=True)# line加总
    qm_user_score = fields.Float(string="QM Score",  digits=(7, 2), store=True)  # line加总
    weight_score = fields.Float(string="Weight Score", digits=(7, 2), store=True)# 加权分数
    finish_date = fields.Char(string="Finish Date")
    state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)  # 识别快照号，标记使用的哪个材料类别/评分区间/失败成本区间的快照
    supplier_company_id = fields.Many2one('iac.supplier.company',  string="Supplier Company")
    vendor_codes = fields.Char(string="Vendor Codes", compute='_taken_vendor_codes')# SC 中参与评核的Vendor Code，多个Vendor Code用逗号隔开
    vendor_types = fields.Char(string='Vendor Types',compute='_taken_vendor_types')#根据vendor_code去register表抓supplier type
    # user_score_cal = fields.Float(string='User Score', compute='_taken_user_score', digits=(7,2))
    scm_user_score_cal = fields.Float(string='SCM Score Cal', compute='_taken_scm_score', digits=(7,2))
    qm_user_score_cal = fields.Float(string='QM Score Cal', compute='_taken_qm_score', digits=(7,2))
    # scm_controller_ids = fields.One2many('iac.score.controller.mapping', 'score_part_category_id', string=u'SCM controller待签核者列表', index=True)
    # qm_controller_ids = fields.One2many('iac.score.controller.mapping', 'score_part_category_id', string=u'QM controller待签核者列表', index=True)
    # scm_leader_ids = fields.One2many('iac.score.leader.mapping', 'score_part_category_id', string=u'SCM leader待签核者列表', index=True)
    # qm_leader_ids = fields.One2many('iac.score.leader.mapping', 'score_part_category_id', string=u'QM leader待签核者列表', index=True)
    scm_state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('approved', 'Approved'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ],string='SCM status', default='scoring')
    qm_state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('approved', 'Approved'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='QM status', default='scoring')
    scm_memo = fields.Text(string='SCM memo')
    qm_memo = fields.Text(string='QM memo')
    scm_leader_id = fields.Many2one('res.partner', string="SCM Leader", domain="[('supplier','=',False)]")
    score_approve_log_ids = fields.One2many('iac.score.approve.log','score_part_category_id')
    buyer_names = fields.Char('Buyer Names',compute='_taken_buyer_names')

    # 试验根据某个字段变化而报错，因为在修改时点save按钮已经将数据写入数据库，就算报错也不能回滚，废弃
    # @api.onchange('user_score')
    # def _onchange_user_score(self):
    #     old_user_score = self.user_score
    #     if self.user_score != self.gr_amount:
    #         self.user_score = old_user_score
    #         raise exceptions.ValidationError(u'不能为空')

    # 重写write方法，使得在修改user_score时报必要的错误
    @api.multi
    def write(self,vals):
        """ controller修改line分数后同时写入到scm_user_score或qm_usre_score和user_score，
         去除对应的检查，将检查放到submit按钮里去"""

        print vals
        change_score = 0
        no_change_score = 0
        id_list = []
        for v in vals['line_ids']:
            if v[2] != False:
                if v[2].has_key('user_score'):
                    change_score += v[2]['user_score']
                elif v[2].has_key('memo') and not v[2].has_key('user_score'):
                    id_list.append(v[1])
            else:
                id_list.append(v[1])
        se_results = self.env['iac.score.part_category.line'].browse(id_list)
        for se_result in se_results:
            no_change_score += se_result.user_score

        for v in vals['line_ids']:
            se_ru = self.env['iac.score.part_category.line'].browse(v[1])
            if se_ru.group_code == 'QM':
                qm_user_score = change_score + no_change_score
                user_score = qm_user_score + self.scm_user_score
                super(IacScorePartCategory,self).write({'qm_user_score': qm_user_score,
                                                        'user_score': user_score})
            elif se_ru.group_code == 'SCM':
                scm_user_score = change_score + no_change_score
                user_score = scm_user_score + self.qm_user_score
                super(IacScorePartCategory, self).write({'scm_user_score': scm_user_score,
                                                         'user_score': user_score})
            break

        # 修改分数时的检查
        # for val in vals['line_ids']:
        #     if val[2] != False:
        #         for line_obj in self.line_ids:
        #             if val[2].has_key('user_score'):
        #                 if line_obj.id == val[1] and val[2]['user_score'] != line_obj.calculate_score and len(val[2]) != 2:
        #                     raise UserError(u'修改User_Score后，如果修改后的分数和Calculate_Score不同，必须填写和修改对应的Memo！')
        #                 elif line_obj.id == val[1] and line_obj.sequence != 11 and (val[2]['user_score'] < 0 or val[2]['user_score'] > line_obj.ratio):
        #                     raise UserError(u'User_Score不能大于Weight,不能小于零！')
        #                 elif line_obj.id == val[1] and line_obj.sequence == 11 and (val[2]['user_score'] < -5 or val[2]['user_score'] > line_obj.ratio):
        #                     raise UserError(u'ISO證書達成情況的User_Score不能大于Weight,不能小于负五！')
        #             else:
        #                 pass

        result = super(IacScorePartCategory,self).write(vals)
        return result

    @api.depends('line_ids','line_ids.user_score')
    def _taken_scm_score(self):
        """ SCM对part_category评分的line加总 """
        for record in self:
            for line_id in record.line_ids:
                record.scm_user_score_cal += line_id.user_score

            # line加总后赋值给scm_user_score
            # super(IacScorePartCategory, record).write({'scm_user_score': record.scm_user_score_cal})
            # self.write()

    @api.depends('line_ids','line_ids.user_score')
    def _taken_qm_score(self):
        """ QM对part_category评分的line加总 """
        print type(self)
        for record in self:
            for line_id in record.line_ids:
                record.qm_user_score_cal += line_id.user_score

            # 计算user_score=record.qm_user_score_cal+record.scm_user_score_cal
            # user_score = record.qm_user_score_cal + record.scm_user_score_cal
            # line加总后赋值给qm_user_score
            # super(IacScorePartCategory, record).write({'qm_user_score': 1})

    # @api.depends('scm_user_score','qm_user_score')
    # def _taken_user_score(self):
    #     """ 对part_category评分的scm_user_score和qm_user_score加总 """
    #
    # #     # user_score=scm_user_score+qm_user_score
    #     super(IacScorePartCategory,self).write({'user_score': self.scm_user_score+self.qm_user_score})

    @api.depends('supplier_company_id','plant_id')
    def _taken_buyer_names(self):
        for v in self:
            domain = [('supplier_company_id', '=', v.supplier_company_id.id)]
            domain += [('plant', '=', v.plant_id.id)]
            vendor_list = self.env["iac.vendor"].search(domain)
            buyer_names = []
            for vendor_rec in vendor_list:
                buyer_names.append((vendor_rec.buyer_email).split('@')[0])
            buyer_names = list(set(buyer_names))
            v.buyer_names = ','.join(buyer_names)

    @api.depends('supplier_company_id','plant_id')
    def _taken_vendor_codes(self):
        for v in self:
            domain=[('supplier_company_id','=',v.supplier_company_id.id)]
            domain+=[('plant','=',v.plant_id.id)]
            vendor_list=self.env["iac.vendor"].search(domain)
            vendor_codes = []
            for vendor_rec in vendor_list:
                vendor_codes.append(vendor_rec.vendor_code)
            v.vendor_codes = ','.join(vendor_codes)

    @api.depends('supplier_company_id', 'plant_id')
    def _taken_vendor_types(self):
        for v in self:
            domain=[('supplier_company_id','=',v.supplier_company_id.id)]
            domain+=[('plant','=',v.plant_id.id)]
            vendor_list=self.env["iac.vendor"].search(domain)
            vendor_types = []
            for vendor_rec in vendor_list:
                vendor_type = self.env['iac.vendor.register'].search([('state','=','done'),('vendor_id','=',vendor_rec.id)]).supplier_type
                if vendor_type:
                    vendor_types.append(vendor_type)
                else:
                    vendor_types.append('N/A')
            v.vendor_types = ','.join(vendor_types)

    def button_search_log(self):
        """ SCM/QM 查询评鉴签核历史 """
        # print sys.path
        for score_record in self:
            # for line_obj in score_record.line_ids:
            #     score_record.env['iac.score.part_category.line'].search()
            action = {
                        'name': _('Approval Log'),
                        'view_mode': 'tree',
                        # 'res_model': self._name,
                        'res_model': 'iac.score.approve.log',
                        'type': 'ir.actions.act_window',
                        'view_id': self.env.ref('iac_vendor_evaluation.view_qm_scm_read_score_history_list').id,
                        # 'act_window_id': self.env.ref('iac_vendor_evaluation.action_view_qm_scm_read_score_history').id,
                        'domain': [('score_part_category_id', '=', score_record.id)],
                        'res_id': score_record.id
                    }
            return action

    @api.multi
    def _check_variety_score(self,record):
        """ 对修改的分数行进行逻辑检查 """
        # print '***********'
        for line_object in record.line_ids:
            if line_object.group_code == 'SCM':
                if line_object.user_score != line_object.calculate_score and not line_object.memo:
                    raise UserError(u'Supplier_Code(%s) Part_Category(%s)的资料明细Sequence为%s修改User_Score后，修改后的分数和Calculate_Score不同，必须填写和对应的Memo！'
                                    %(line_object.supplier_company_id.company_no,line_object.part_category_id.name,line_object.seq_no))
                elif line_object.user_score < 0 or line_object.user_score > line_object.ratio:
                    raise UserError(u'Supplier_Code(%s) Part_Category(%s)的资料明细Sequence为%s的User_Score不能大于Weight,不能小于零！'
                                    %(line_object.supplier_company_id.company_no,line_object.part_category_id.name,line_object.seq_no))
                # elif line_object.sequence == 11 and (line_object.user_score < -5 or line_object.user_score > line_object.ratio):
                #     raise UserError(u'资料明细Sequence为%s的ISO證書達成情況的User_Score不能大于Weight,不能小于负五！'%(line_object.sequence,))
            else:
                if line_object.user_score != line_object.calculate_score and not line_object.memo:
                    raise UserError(u'Supplier_Code(%s) Part_Category(%s)的资料明细Sequence为%s修改User_Score后，修改后的分数和Calculate_Score不同，必须填写和对应的Memo！'
                                    %(line_object.supplier_company_id.company_no,line_object.part_category_id.name,line_object.seq_no))
                elif line_object.code != 'QM11' and (line_object.user_score < 0 or line_object.user_score > line_object.ratio):
                    raise UserError(u'Supplier_Code(%s) Part_Category(%s)的资料明细Sequence为%s的User_Score不能大于Weight,不能小于零！'
                                    %(line_object.supplier_company_id.company_no,line_object.part_category_id.name,line_object.seq_no))
                elif line_object.code == 'QM11' and (line_object.user_score < -5 or line_object.user_score > 5):
                    raise UserError(u'Supplier_Code(%s) Part_Category(%s)的资料明细Sequence为%s的ISO證書達成情況的User_Score不能大于五,不能小于负五！'
                                    %(line_object.supplier_company_id.company_no,line_object.part_category_id.name,line_object.seq_no))

    def _insert_vendor_score_log(self,record,approve_role,approve_status,memo):
        score_log_val = {
            'score_snapshot': record.sudo().score_snapshot,
            'score_part_category_id': record.sudo().id,
            'user_id': self._uid,
            'approve_role': approve_role,
            'approve_status': approve_status,
            'memo': memo,
            'part_category_id': record.sudo().part_category_id.id,
            'user_score': record.sudo().user_score
        }
        self.env['iac.score.approve.log'].create(score_log_val)

    @api.multi
    def action_batch_submit(self):
        """
        SCM/QM controller 调整分数并且submit给SCM Leader审核
        :return:
        """

        for record in self:
            # 添加对修改的分数进行逻辑检查
            self._check_variety_score(record)
            try:
                # score_id_list = []
                # score_id_list.append(record.sudo().score_list_id.id)
                for item in self.env.user.groups_id:
                    if item.name == 'SCM controller':
                        # 更新iac.score.part_category中的scm/qmcontroller为实际的提交的user partner id
                        # 判断scm controller是否调整了分数
                        line_lens = 0
                        for line_obj in record.line_ids:
                            if line_obj.calculate_score != line_obj.user_score:
                                break
                            else:
                                line_lens += 1
                        if len(record.line_ids) == line_lens:
                            # 未调整分数 scm_state=done，不用scm leader审核
                            # super(IacScorePartCategory,record).write({'scm_state': 'done',
                            #               'scm_controller_id': self.env.user.partner_id.id})
                            if record.qm_state =='done':
                                super(IacScorePartCategory, record).write({'scm_state': 'done',
                                                                           'state': 'done',
                                                                           'scm_controller_id': self.env.user.partner_id.id})
                            else:
                                super(IacScorePartCategory, record).write({'scm_state': 'done',
                                                                           'scm_controller_id': self.env.user.partner_id.id})

                            # 调用插入分数Log表的方法
                            self._insert_vendor_score_log(record,'scm_controller', 'approve', u'SCM CONTROLLER送签成功')

                            # 判断当前SC所有的score.part_category是不是都是done，调用现有方法judge_last_action()
                            # obj = IacScorePartCategoryInherit()
                            # obj.judge_last_action(record,'scm_controller')
                            # 调用方法更改iac.class.part_category状态为done
                            self.env['iac.score.part_category.inherit'].modify_class_state(record)
                            self.env['iac.score.part_category.inherit'].judge_last_action(record,'scm_controller')
                        else:
                            # 调整了分数，scm_state = to_approve
                            super(IacScorePartCategory, record).write({'scm_state': 'to approve',
                                          'scm_controller_id': self.env.user.partner_id.id})

                            # 调用插入分数Log表的方法
                            self._insert_vendor_score_log(record,'scm_controller', 'approve', u'SCM CONTROLLER送签成功')
                    elif item.name == 'QM controller':
                        # 更新iac.score.part_category中的scm/qmcontroller为实际的提交的user partner id
                        # 判断qm controller是否调整了分数
                        line_lens = 0
                        for line_obj in record.line_ids:
                            if line_obj.calculate_score != line_obj.user_score:
                                break
                            else:
                                line_lens += 1
                        if len(record.line_ids) == line_lens:
                            # 未调整分数 qm_state=done，不用scm leader审核
                            # super(IacScorePartCategory, record).write({'qm_state': 'done',
                            #               'qm_controller_id': self.env.user.partner_id.id})
                            if record.scm_state =='done':
                                super(IacScorePartCategory, record).write({'qm_state': 'done',
                                                                           'state': 'done',
                                                                           'qm_controller_id': self.env.user.partner_id.id})
                                # self.env.cr.commit()
                            else:
                                super(IacScorePartCategory, record).write({'qm_state': 'done',
                                                                           'qm_controller_id': self.env.user.partner_id.id})
                                # self.env.cr.commit()

                            # 调用插入分数Log表的方法
                            self._insert_vendor_score_log(record,'qm_controller', 'approve', u'QM CONTROLLER送签成功')
                            # 判断当前SC所有的score.part_category是不是都是done，调用现有方法judge_last_action()
                            # obj = IacScorePartCategoryInherit()
                            # obj.judge_last_action(record,'scm_controller')
                            # 调用方法更改iac.class.part_category状态为done
                            self.env['iac.score.part_category.inherit'].modify_class_state(record)
                            self.env['iac.score.part_category.inherit'].judge_last_action(record, 'qm_controller')

                        else:
                            # 调整了分数，qm_state=to_approve
                            super(IacScorePartCategory, record).write({'qm_state': 'to approve',
                                          'qm_controller_id': self.env.user.partner_id.id})

                            # 调用插入分数Log表的方法
                            self._insert_vendor_score_log(record,'qm_controller','approve',u'QM CONTROLLER送签成功')
            except:
                self.env.cr.rollback()
                # TaskVendorScore.insert_score_approve_log(record.score_list_id, record.score_snapshot, 'scm_controller','approve', u'SCM CONTROLLER送签失败')
                raise exceptions.ValidationError(traceback.format_exc())

        message = u'提交成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    # @api.multi
    # def write(self,vals):
    #     """
    #     执行评核人员校验
    #     :param vals:
    #     :return:
    #     """
    #     result=super(IacScorePartCategory,self).write(vals)
    #
    #     if "scm_partner_id" in vals:
    #         scm_group=self.env.user.groups_id.filtered(lambda x:x.name=='SCM controller')
    #         if not scm_group.exists():
    #             raise UserError('必须是SCM Controller 才能设置 SCM User')
    #         for part_line in self:
    #             if part_line.scm_controller_id.id<>self.env.user.partner_id.id:
    #                 raise UserError(u"不能修改没有分配给自己的记录")
    #
    #     if "qm_partner_id" in vals:
    #         scm_group=self.env.user.groups_id.filtered(lambda x:x.name=='QM controller')
    #         if not scm_group.exists():
    #             raise UserError('必须是QM Controller 才能设置 QM User')
    #         for part_line in self:
    #             if part_line.qm_controller_id.id<>self.env.user.partner_id.id:
    #                 raise UserError(u"不能修改没有分配给自己的记录")
    #
    #
    #     return result
    #     pass

    # @api.model
    # def create(self,vals):
    #     result=super(IacScorePartCategory,self).create(vals)
    #     return result

    # 不能注释
    def update_part_category_score_data(self):
        """
        提供给外部调用,只能由score.part.category 单笔记录调用,计算当前类别的入料总数和入料金额(不分厂区)
        :return:
        """
        self._update_part_category_score_data()

    # 不能注释
    def _update_part_category_score_data(self):
        """
        只能由score.part.category 单笔记录调用,计算当前类别的入料总数和入料金额(不分厂区)
        :return:
        """
        user_score_sum = 0
        scm_user_score=0
        qm_user_score=0
        update_vals={
            "weight":0
        }

        #获取同一个材料类别的跨厂区的当前批次的入料金额
        self.env.cr.execute("""
            SELECT
               COALESCE(SUM (gr_amount),0) gr_amount_sum
            FROM
                iac_score_part_category
            WHERE
                score_snapshot =%s
            AND supplier_company_id =%s
            AND part_category_id =%s
                        """,(self.sudo().score_snapshot,self.sudo().supplier_company_id.id,self.sudo().part_category_id.id))
        pg_result = self.env.cr.dictfetchone()
        gr_amount_sum=pg_result["gr_amount_sum"]

        update_vals={}
        if gr_amount_sum==0:
            update_vals["weight"]=0.0
        else:
            update_vals["weight"]=self.sudo().gr_amount/gr_amount_sum

        #获取同厂区的所有材料类别的入料数量
        self.env.cr.execute("""
            SELECT
               COALESCE(SUM (gr_qty),0) gr_qty_sum
            FROM
                iac_score_part_category
            WHERE
                score_snapshot =%s
            AND supplier_company_id =%s
            AND plant_id =%s
                        """,(self.sudo().score_snapshot,self.sudo().supplier_company_id.id,self.sudo().plant_id.id))
        pg_result = self.env.cr.dictfetchone()
        gr_qty_sum=pg_result["gr_qty_sum"]

        if gr_qty_sum==0:
            update_vals["gr_qty_weight"]=0
        else:
            update_vals["gr_qty_weight"]=self.sudo().gr_qty/gr_qty_sum


        for line in self.sudo().line_ids:
            user_score_sum += line.user_score
            if line.group_code == 'SCM':
                scm_user_score+=line.user_score
            if line.group_code == 'QM':
                qm_user_score+=line.user_score
        update_vals["user_score"]=user_score_sum
        update_vals["scm_user_score"]=scm_user_score
        update_vals["qm_user_score"]=qm_user_score
        update_vals["weight_score"] = user_score_sum * update_vals["weight"]
        #当前材料类别记录分数和材料大类等信息
        # super(IacScorePartCategory, self).write(update_vals)
        # 因为ir_rule的原因，改用sql语句来更新记录
        self.env.cr.execute("""
                    update iac_score_part_category spc 
                        set weight = %s,
                            gr_qty_weight = %s,
                            user_score = %s,
                            scm_user_score = %s,
                            qm_user_score = %s,
                            weight_score = %s
                        where id = %s
                                """,(update_vals["weight"],update_vals["gr_qty_weight"],update_vals["user_score"],update_vals["scm_user_score"],update_vals["qm_user_score"],update_vals["weight_score"],self.sudo().id))
        # self.env.cr.commit()

    def update_part_category_score_data_ref(self):
        """
        提供给外部调用
        """
        self._update_part_category_score_data_ref()

    def _update_part_category_score_data_ref(self):
        """
        只能由score.part.category 单笔记录调用,计算当前类别的入料总数和入料金额(不分厂区)
        只能在全部评分完毕的情况下调用这个方法
        级联更新分数信息
        更新顺序如下
        iac.score.part_category
        iac.class.part_category
        iac.score.supplier_company
        iac.class.supplier_company

        更新分数相关的数据
        """
        #更新当前记录的 user_score scm_user_score qm_user_score weight_score
        self._update_part_category_score_data()

        #只有在全部厂的part_category都评分结束的情况下才进行级联更新 class_part_category的数据
        domain=[
            ('supplier_company_id','=',self.supplier_company_id.id),
            ('part_category_id','=',self.part_category_id.id),
            ('score_snapshot','=',self.score_snapshot),
            ('state','=','scoring')
        ]
        score_part_list=self.env["iac.score.part_category"].search(domain,limit=1)
        #如果全部厂的score_part_category都评分过以后，才能进行级联更新
        if not score_part_list:
            self.class_part_category_id._update_class_part_category_data_ref()
            class_vals={
                "part_category_class":self.class_part_category_id.final_part_class
            }
            self.write(class_vals)

    # @api.multi
    # def _compute_weight(self):
    #     for score in self:
    #         sum_qty = 0
    #         # 各plant的入料批次汇总
    #         score_part_category_ids = self.env['iac.score.part_category'].search(
    #             [('supplier_company_id', '=', score.supplier_company_id.id),
    #              ('part_category_id', '=', score.part_category_id.id),
    #              ('score_snapshot', '=', score.score_snapshot)])
    #         for part_category_score in score_part_category_ids:
    #             sum_qty += part_category_score.gr_qty
    #
    #         if sum_qty > 0:
    #             score.weight = score.gr_qty / sum_qty
    #         else:
    #             score.weight = 0

    # @api.depends('user_score', 'weight')
    # def _compute_weight_score(self):
    #     for score in self:
    #         score.weight_score = score.user_score * score.weight

    # @api.depends('line_ids.user_score')
    # def _compute_user_score(self):
    #     for score in self:
    #         sum_score = 0
    #         for line in score.line_ids:
    #             if score.plant_id == line.plant_id:
    #                 sum_score += line.user_score
    #         score.user_score = sum_score

    # @api.depends('line_ids.group_code', 'line_ids.user_score')
    # def _compute_scm_user_score(self):
    #     for score in self:
    #         sum_score = 0
    #         for line in score.line_ids:
    #             if score.plant_id == line.plant_id and line.group_code == 'SCM':
    #                 sum_score += line.user_score
    #         score.scm_user_score = sum_score

    # @api.depends('line_ids.group_code', 'line_ids.user_score')
    # def _compute_qm_user_score(self):
    #     for score in self:
    #         qm_score = 0
    #         for line in score.line_ids:
    #             if score.plant_id == line.plant_id and line.group_code == 'QM':
    #                 qm_score += line.user_score
    #         score.qm_user_score = qm_score

    # @api.depends('supplier_company_id', 'part_category_id', 'score_snapshot')
    # def _compute_part_category_class(self):
    #     for pc_class in self:
    #         domain = [('supplier_company_id', '=', pc_class.supplier_company_id.id),
    #                   ('part_category_id', '=', pc_class.part_category_id.id),
    #                   ('score_snapshot', '=', pc_class.supplier_company_id.score_snapshot)]
    #         part_category_class_ids = self.env['iac.class.part_category'].search_read(domain, ['final_part_class'])
    #         if part_category_class_ids:
    #             pc_class.part_category_class = part_category_class_ids[0]['final_part_class']

    # @api.multi
    # def action_batch_user_scoring(self):
    #     int_part_class_id = 0
    #     part_class_name = ''# user选择打分的材料大类
    #     int_part_category_ids = []# 待打分的材料类别id
    #     for part_category_id in self:
    #         if part_category_id.state != 'scoring':
    #             raise UserError(_(u'已评过分的材料类别不能再次评分！'))
    #         if  tools.config.get('dummy_interface',False):
    #            pass
    #         else:
    #             #非测试模式就需要检查当前操作员是否符合条件
    #             if self.env.user.login <> 'admin': # admin 帳號 不用卡權限
    #                 if not (self.env.user.partner_id.id in [self.scm_partner_id.id,self.qm_partner_id.id]):
    #                     raise UserError(_(u"只有指定的评分人员才能进行打分操作"))
    #
    #         if part_class_name == '':
    #             int_part_class_id = part_category_id.part_class.id
    #             part_class_name = part_category_id.part_class.name
    #             int_part_category_ids.append(part_category_id.id)
    #         else:
    #             if part_category_id.part_class.name == part_class_name:
    #                 int_part_category_ids.append(part_category_id.id)
    #             else:
    #                 raise UserError(_(u'您选择了不同材料大类。同一材料大类才可以一起评分！'))
    #
    #     if len(int_part_category_ids) > 0:
    #         part_category_line_ids = []# 同一材料大类SCM/QM评分项
    #         # 根据用户项目组过滤评分项
    #         group_code = ''
    #         if self.env.user in self.env.ref('oscg_vendor.group_scm_user').users:
    #             group_code = 'SCM'
    #         elif self.env.user in self.env.ref('oscg_vendor.group_qm_user').users:
    #             group_code = 'QM'
    #         part_category_id = self.env['iac.score.part_category'].browse(int_part_category_ids[0])
    #         for item in part_category_id.line_ids:
    #             if item.vs_def_id.group_code == group_code and item.vs_def_id.part_class.id == int_part_class_id:
    #                 part_category_line_ids.append(item.id)
    #
    #         request.session['scoring_part_category_ids'] = int_part_category_ids# 将用户选择的评分类别存入session
    #         action = {
    #             'domain': [('id', 'in', part_category_line_ids)],
    #             'name': _('Part Category Scoring'),
    #             'type': 'ir.actions.act_window',
    #             'view_type': 'form',
    #             'view_mode': 'tree,form',
    #             'res_model': 'iac.score.part_category.line'
    #         }
    #         return action


class IacScorePartCategoryInherit(models.Model):
    _inherit = 'iac.score.part_category'
    _name = 'iac.score.part_category.inherit'
    _table = 'iac_score_part_category'

    def write(self, vals):
        """ 重写write方法，调用原始第一层父类的write方法，当leader核准分数时，Disapprove,必须填写Memo """

        result = super(IacScorePartCategory, self).write(vals)
        return result

    def leader_approve_score(self):
        """ leader核准分数，重新计算分数和等级，approve动作 """


        for record in self:
            try:
                # score_id_list = []
                # score_id_list.append(record.score_list_id.id)
                for item in self.env.user.groups_id:
                    if item.name=='SCM leader':
                        # 更新iac.score.part_category中的scm/qm leader 为实际的user partner id
                        record.write({'scm_state': 'done',
                                      'scm_leader_id': self.env.user.partner_id.id})
                        # 调用插入分数Log表的方法
                        self.env['iac.score.part_category']._insert_vendor_score_log(record,'scm_leader', 'approve', u'SCM Leader送签成功')

                        # 如果QM leader已经签核过了并且qm_state是done的时候，修改整条记录的state为done
                        if record.sudo().qm_state == 'done':
                            spc_obj = self.env['iac.score.part_category'].sudo().browse(record.sudo().id)
                            super(IacScorePartCategory, spc_obj).write({'state': 'done'})
                            # super(IacScorePartCategoryInherit, record).write({'state': 'done'})
                            # 调用方法更改iac.class.part_category状态为done
                            self.modify_class_state(record)
                            # 判断属于这个company是不是签核流程最后一个动作，如果是就调用方法重新计算对应的分数和等级
                            self.judge_last_action(record,'scm_leader')

                    elif item.name=='QM Leader':
                        # 更新iac.score.part_category中的scm/qm leader 为实际的user partner id
                        record.write({'qm_state': 'done',
                                      'qm_leader_id': self.env.user.partner_id.id})
                        # 调用插入分数Log表的方法
                        self.env['iac.score.part_category']._insert_vendor_score_log(record,'qm_leader', 'approve', u'QM Leader送签成功')

                        # 如果SCM leader已经签核过了并且scm_state是done的时候，修改整条记录的state为done
                        if record.sudo().scm_state == 'done':
                            spc_obj = self.env['iac.score.part_category'].sudo().browse(record.sudo().id)
                            super(IacScorePartCategory, spc_obj).write({'state': 'done'})
                            # self.env.cr.commit()
                            # 调用方法更改iac.class.part_category状态为done
                            self.modify_class_state(record)
                            # 判断属于这个company是不是签核流程最后一个动作，如果是就调用方法重新计算对应的分数和等级
                            self.judge_last_action(record,'qm_leader')

            except:
                self.env.cr.rollback()
                raise exceptions.ValidationError(traceback.format_exc())

        message = u'提交成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    def leader_disapprove_score(self):
        """
        leader核准分数，disapprove动作
        :return:
        """

        for record in self:
            # score_id_list = []
            # score_id_list.append(record.score_list_id.id)
            for item in self.env.user.groups_id:
                if item.name == 'SCM leader':
                    # 判断是否填写memo
                    if not record.scm_memo:
                        raise UserError(u'Disapprove时请填写SCM memo')
                    # 更新iac.score.part_category中的scm/qm leader 为实际的user partner id
                    try:
                        record.write({'scm_state': 'disapprove',
                                      'scm_leader_id': self.env.user.partner_id.id})
                        # 调用插入分数Log表的方法
                        self.env['iac.score.part_category']._insert_vendor_score_log(record,'scm_leader','disapprove',u'SCM leader 退回评鉴分数重评')

                    except:
                        self.env.cr.rollback()
                        raise exceptions.ValidationError(traceback.format_exc())
                elif item.name == 'QM Leader':
                    # 判断是否填写memo
                    if not record.qm_memo:
                        raise UserError(u'Disapprove时请填写QM memo')
                    try:
                        # 更新iac.score.part_category中的scm/qm leader 为实际的user partner id
                        record.write({'qm_state': 'disapprove',
                                      'qm_leader_id': self.env.user.partner_id.id})
                        # 调用插入分数Log表的方法
                        self.env['iac.score.part_category']._insert_vendor_score_log(record,'qm_leader','disapprove',u'QM leader 退回评鉴分数重评')

                    except:
                        self.env.cr.rollback()
                        raise exceptions.ValidationError(traceback.format_exc())

        message = u'退件成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @odoo_env
    def _insert_vendor_class_log(self,**kwargs):
        record = kwargs.get('record')
        approve_role = kwargs.get('approve_role')
        action = kwargs.get('action')
        memo = kwargs.get('memo')
        class_supplier_company_obj = self.env['iac.class.supplier_company'].search(
            [('score_snapshot', '=', record.sudo().score_snapshot), ('supplier_company_id', '=', record.sudo().supplier_company_id.id)])
        class_log_vals = {
            'score_snapshot': record.sudo().score_snapshot,
            'class_supplier_company_id': class_supplier_company_obj.id,
            'user_id': self._uid,
            'approve_role': approve_role,
            'action': action,
            'memo': memo,
            'user_class': class_supplier_company_obj.user_class
        }
        self.env['iac.class.approve.log'].create(class_log_vals)

    def judge_last_action(self,record,approve_leader):
        """
        判断属于这个company是不是签核流程最后一个动作，如果是就调用方法重新计算对应的分数和等级
        :param record:
        :return:
        """
        # re_score_list = []
        # for re in record:
        #     re_score_list.append(re.sudo().score_list_id.id)
        company_objs = self.env['iac.score.part_category'].sudo().search([('supplier_company_id', '=', record.sudo().supplier_company_id.id),
                                    ('score_snapshot', '=', record.sudo().score_snapshot)])
        x = 0
        for company_obj in company_objs:
            if company_obj.scm_state != 'done' or company_obj.qm_state != 'done':
                x += 1
                break
            else:
                continue
        if x == 0:
            self.again_calculate_score(record)
            self.again_calculate_class(record.sudo().class_part_category_id)
            # 判断最后class是否为D
            final_class_obj = self.env['iac.class.supplier_company'].search([('supplier_company_id','=',record.sudo().supplier_company_id.id),
                                                                             ('score_snapshot', '=', record.sudo().score_snapshot)])
            # 如果user_class为D，mail通知 scm controller提交审核
            if final_class_obj.user_class == 'D':
                # 调用方法插入class Log表
                memo = u'SCM/QM Leader核准后重新计算class为D，分数过低产生D class评核'
                self._insert_vendor_class_log(record,approve_leader,'SCM/QM Leader核准后重新计算class',memo)
                self._mail_to_scm_controller(record)
            else:
                # 如果上次评鉴的等级不为D，并且user_class和current_class不同时才去更新SC.current_class,并且call SAP vendor_006接口更新state=done
                jiekou_kwargs = {'supplier_company_id': final_class_obj.supplier_company_id,
                                 'user_class': final_class_obj.user_class,
                                 'nub': '1',
                                 'score_snapshot': final_class_obj.score_snapshot}
                if record.sudo().supplier_company_id.current_class != 'D' and record.sudo().supplier_company_id.current_class != final_class_obj.user_class:
                    t = threading.Thread(target=self.jiekou_thread, kwargs=jiekou_kwargs)
                    t.setDaemon(True)
                    t.start()
                    t.join()

                # 如果上次评鉴是D class，user_class不为D，要同时call SAP vendor_005和vendor_006接口
                elif record.sudo().supplier_company_id.current_class == 'D':
                    t = threading.Thread(target=self.jiekou_thread,kwargs=jiekou_kwargs)
                    t.setDaemon(True)
                    t.start()
                    t.join()


                # 等级不为D的只需要插入class Log不需要发送邮件
                log_kwargs = {'record':record,
                              'approve_leader': approve_leader,
                              'action': 'SCM/QM Leader核准后重新计算class',
                              'memo': 'SCM/QM Leader核准后重新计算class不为D，分数合格无需继续审核class',}
                self._insert_vendor_class_log(**log_kwargs)

    @odoo_env
    def jiekou_thread(self,**kwargs):
        supplier_company_id = kwargs.get('supplier_company_id')
        user_class = kwargs.get('user_class')
        nub = kwargs.get('nub')
        score_snapshot = kwargs.get('score_snapshot')
        update_result = self.env['iac.class.supplier_company'].call_sap_change_sc_class_update(
                                            supplier_company_id, user_class, nub, score_snapshot)

        if update_result != True:
            raise exceptions.ValidationError(traceback.format_exc())

    def _mail_to_scm_controller(self,record):
        """
        D class的厂商 ，发送邮件给所有的SCM CONTROLLER
        :param record:
        :return:
        """
        # 查询到所有的SCM CONTROLLER
        sql_str = """
                    select ru.id,rg.name,ru.login,rp.email
                        from res_groups rg inner join res_groups_users_rel gu on gu.gid = rg.id 
                        inner join res_users ru on ru.id = gu.uid
                        inner join res_partner rp on rp.id = ru.partner_id                      
                        where rg.name = %s
                        and ru.active = 't'
                        """
        self.env.cr.execute(sql_str,('SCM controller',))
        sc_results = self.env.cr.dictfetchall()
        email_list = []
        # 如果查询到结果就发邮件给SCM CONTROLLER
        if sc_results:
            for sc_result in sc_results:
                email_list.append(sc_result['email'])
                email = ';'.join(email_list)
                body_list = [[record.sudo().supplier_name,record.sudo().supplier_code,record.sudo().vendor_codes,'D']]
                # 调用通用的发送邮件的方法
                self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email, "", "以下 D CLASS厂商请确认",
                                ['Company_name','Company_no','Vendors','Class'], body_list, "VENDOR_EVALUATION")

        # 未查询到结果就发邮件给IT内部人员
        else:
            email = 'Zhang.Pei-Wu@iac.com.tw' + ';' + 'Wang.Ningg@iac.com.tw' + ';' + 'jiang.shier@iac.com.tw'
            body_list = [[record.sudo().supplier_name, record.sudo().supplier_code, record.sudo().vendor_codes, 'D']]
            self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email, "", "以下 D CLASS厂商请确认(邮件发送异常)",
                            ['Company_name', 'Company_no', 'Vendors', 'Class'],body_list, "VENDOR_EVALUATION")

    def modify_class_state(self,record):
        """
        如果class_part_category对应的各个厂区的状态都是done的时候，class state变为done
        :param record:
        :return:
        """
        class_objs = self.env['iac.score.part_category'].sudo().search([('class_part_category_id', '=', record.sudo().class_part_category_id.id)])
        # class_objs = self.sudo().search([('class_part_category_id', '=', record.sudo().class_part_category_id.id)])
        i = 0
        for class_obj in class_objs:
            if class_obj.state == 'done':
                i += 1
        # 如果class_part_category对应的各个厂区的状态都是done的时候，class state变为done
        if i == len(class_objs):
            se_result = self.env['iac.class.part_category'].browse(record.sudo().class_part_category_id.id)
            se_result.write({'state': 'done'})

    def again_calculate_score(self,record):
        # 重新计算iac.score.part_category: update_part_category_score_data()
        # IacScorePartCategory.update_part_category_score_data()
        for score_obj in self.env['iac.score.part_category'].sudo().search([('supplier_company_id', '=', record.sudo().supplier_company_id.id),
                                                                            ('score_snapshot', '=',record.sudo().score_snapshot)]):
            score_obj.update_part_category_score_data()

    def again_calculate_class(self,record):
        # 1.重新计算iac.class.part_caetgory: update_class_part_category_data_ref
        # 2.内部再call iac.score.supplier_company: update_score_company_data_ref
        # 3.再级联更新iac.class.supplier_company
        # IacClassPartCategory.update_class_part_category_data_ref()
        i = 1
        score_pc = record.search([('supplier_company_id', '=', record.supplier_company_id.id),
                       ('score_snapshot', '=', record.score_snapshot)])
        for class_obj in score_pc:
            class_obj.update_class_part_category_data_ref(i,len(score_pc))
            i += 1


class IacScorePartCategoryLine(models.Model):
    """
    材料类别评分项
    对应根据score Definition生成的某个材料类别评分项目表 vs_sum_score

    四级评分信息表
    Supplier Company+part_category_id+vs_def_id
    """
    _name = 'iac.score.part_category.line'
    _description = "Vendor Score Part Category Line"
    _order = "group_code, seq_no"

    score_part_category_id = fields.Many2one('iac.score.part_category', string="Score Part Category")
    #supplier_company_id = fields.Many2one('iac.supplier.company', related="score_part_category_id.supplier_company_id", string="Supplier Company")
    #plant_id = plant = fields.Many2one('pur.org.data', related="score_part_category_id.plant_id", string="Plant")
    plant_id = plant = fields.Many2one('pur.org.data',  string="Plant")
    #part_category_id = fields.Many2one('iac.part.category', related="score_part_category_id.part_category_id", string="Part Category")# 评核的材料类别
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")# 评核的材料类别
    vs_def_id = fields.Many2one('iac.score.definition', string="Vendor Score Definition")
    group_code = fields.Selection([
        ('SCM', 'SCM'),
        ('QM', 'QM')], related='vs_def_id.group_code')
    code = fields.Char(related='vs_def_id.code')
    seq_no = fields.Integer(string="Sequence", related='vs_def_id.seq_no')
    description = fields.Char('Description', related='vs_def_id.description')
    score_standard = fields.Char('Score Standard', related='vs_def_id.score_standard')
    ratio = fields.Integer('Weight', related='vs_def_id.ratio')
    score_value = fields.Char(string="Value")# 该指标项的计算值，用于到参考区间表取值
    calculate_score = fields.Float(string="Calculate Score", digits=(7, 2))# 系统自动计算出的分数，供user在评分时参考
    user_score = fields.Float(string="User Score", digits=(7, 2))  # user评分
    scm_partner_id = fields.Many2one('res.partner', related="score_part_category_id.scm_partner_id", string="SCM User")
    scm_memo = fields.Text(string="SCM Memo")
    qm_partner_id = fields.Many2one('res.partner', related="score_part_category_id.qm_partner_id", string="QM User")
    qm_memo = fields.Text(string="QM Memo")
    state = fields.Selection([
        ('scoring', 'Scoring'),
        ('to approve', 'To Approve'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)  # 识别快照号，标记使用的哪个材料类别/评分区间/失败成本区间的快照
    supplier_company_id = fields.Many2one('iac.supplier.company',  string="Supplier Company")
    score_list_id = fields.Many2one('iac.score.list', string="Score List")  # 评核名单
    vendor_codes = fields.Char(string="Vendor Codes", compute='_taken_vendor_codes')# SC 中参与评核的Vendor Code，多个Vendor Code用逗号隔开
    memo = fields.Text(string='Memo')


    @api.depends('supplier_company_id','plant_id')
    def _taken_vendor_codes(self):
        for v in self:
            domain=[('supplier_company_id','=',v.supplier_company_id.id)]
            domain+=[('plant','=',v.plant_id.id)]
            vendor_list=self.env["iac.vendor"].search(domain)
            vendor_codes = []
            for vendor_rec in vendor_list:
                vendor_codes.append(vendor_rec.vendor_code)
            v.vendor_codes = ','.join(vendor_codes)
    #
    # @api.multi
    # def write(self,vals):
    #     """
    #     执行评核人员校验
    #     :param vals:
    #     :return:
    #     """
    #     result=super(IacScorePartCategoryLine,self).write(vals)
    #     if "user_score" in vals:
    #         self._check_user_score()
    #
    #     #进行数据校验
    #     return result
    #
    # # 检查打分是否合法
    # def _check_user_score(self):
    #     for record in self:
    #         if record.user_score:
    #             if record.user_score > record.ratio:
    #                 raise ValidationError(_(u'分值不能大于权重！'))
    #     #校验分数
    #     for part_score_line in self:
    #         if part_score_line.vs_def_id.group_code =='QM' and part_score_line.vs_def_id.sequence in [11]:
    #             if part_score_line.user_score<-5.0:
    #                 raise UserError(u"%s 不允许分数小于-5"%(part_score_line.vs_def_id.description,))
    #             else:
    #                 continue
    #         if part_score_line.vs_def_id.group_code =='QM' and part_score_line.vs_def_id.sequence in [12]:
    #             if part_score_line.user_score<-3.0:
    #                 raise UserError(u"%s 不允许分数小于-3"%(part_score_line.vs_def_id.description,))
    #             else:
    #                 continue
    #         #if round(part_score_line.user_score)<0.0:
    #         #    raise UserError(u"%s 不允许分数小于0"%(part_score_line.vs_def_id.description,))
    #
    #
    # # user打分，最终提交
    # @api.multi
    # def action_batch_submit(self):
    #     # 将user选择的part category line的状态置成to approve
    #     for item in self:
    #         if item.state == 'scoring':
    #             item.state = 'to approve'
    #             if not item.user_score:
    #                 item.user_score = 0
    #     return self.sudo()._after_user_scoring_lwt()
    #     #return self._after_user_scoring()
    #
    # def _after_user_scoring_lwt(self):
    #     """
    #     如果part category line都评完分，则设置对应的part category为to approve
    #     :return:
    #     """
    #
    #
    #     # 将user在上一步选择的part category的评分设置成跟当前part category一样
    #     int_other_score_pc_ids = []
    #     # 从session中获取上一个操作用户存放的评分类别
    #     int_score_pc_ids = request.session.get('scoring_part_category_ids')
    #     if int_score_pc_ids:
    #         # 将当前评分的part category从int_part_category_ids中排除
    #         current_score_pc_id = self[0].score_part_category_id
    #         #current_score_pc_rec=self.env['iac.score.part_category'].browse(current_score_pc_id)
    #         #当前评分的条目状态变更为已经提交
    #         self.write({"state":"to approve"})
    #
    #         #判断是否所有材料类别的条目都评分完毕
    #         score_pc_line_rec=current_score_pc_id.line_ids.filtered(lambda x:(x.state!="to approve"))
    #         #如果全部评分完毕,那么变更材料类别评分状态
    #         if not score_pc_line_rec.exists():
    #             current_score_pc_id.write({"state":"to approve"})
    #             current_score_pc_id._update_part_category_score_data_ref()
    #         else:
    #             #只更新当前已经打分的部分
    #             current_score_pc_id._update_part_category_score_data()
    #
    #
    #     request.session['scoring_part_category_ids'] = []  # 将用户选择的评分类别清空
    #     action = {
    #         'domain': [('id', 'in', int_score_pc_ids)],
    #         'name': _('Part Category Scoring'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'tree,form',
    #         'res_model': 'iac.score.part_category'
    #     }
    #     return action

class IacScorePartCategoryClass(models.Model):
    """
    Vendor材料类别分数，配合class使用，不执行记录规则
    """
    _name = 'iac.class.score.part_category'
    _inherit = 'iac.score.part_category'
    _table = 'iac_score_part_category'

class IacClassSupplierCompany(models.Model):
    """
    Supplier Company评核等级表
    一个class数据对应多个score数据
    一级评分信息表:
    Supplier Company 评分
    """
    _name = 'iac.class.supplier_company'
    _description = "Supplier Company Class"
    _order = "id desc"

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    current_class = fields.Selection(related="supplier_company_id.current_class", string="Current Class", readonly=True)
    score_supplier_company_ids = fields.One2many('iac.class.score.supplier_company', 'class_supplier_company_id', string="Supplier Company Site Score")
    class_part_category_ids = fields.One2many('iac.class.part_category', 'class_supplier_company_id', string="Part Category Class")
    #calculate_score = fields.Float(string="Calculate Score", compute="_compute_calculate_supplier_score", digits=(7, 2), store=True)# 加权分数
    calculate_score = fields.Float(string="Calculate Score",digits=(7, 2), store=True)# 加权分数
    #calculate_class = fields.Selection([
    #    ('A', 'A'),
    #    ('B', 'B'),
    #    ('C', 'C'),
    #    ('D', 'D'),
    #    ('DW', 'DW'),
    #], compute="_compute_calculate_supplier_class", string="Calculate Class", store=True)
    calculate_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ],  string="Calculate Class", store=True)
    #final_class = fields.Selection([
    #    ('A', 'A'),
    #    ('B', 'B'),
    #    ('C', 'C'),
    #    ('D', 'D'),
    #    ('DW', 'DW'),
    #], compute="_compute_final_supplier_class", string="Final Class", store=True)# 直接取calculate class，不需要scm controller确认

    final_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ],string="Final Class", store=True)# 直接取calculate class，不需要scm controller确认
    scm_controller_id = fields.Many2one('res.partner', string="SCM Controller", domain="[('supplier','=',False)]")
    scm_memo = fields.Text(string="SCM Controller Memo")
    qm_controller_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    qm_leader_id = fields.Many2one('res.partner', string="QM Leader", domain="[('supplier','=',False)]")
    qm_memo = fields.Text(string="QM Leader Memo")
    state = fields.Selection([
        ('scoring', 'Scoring'),#这个状态目前没有用,可能未来废弃
        ('in_review', 'In Review'),
        ('to approve', 'To Approve'),# 如果call sap失败仍停留在to approve状态，可以再次审核
        ('scm_ctl_disapproved', 'SCM Controller Disapproved'),
        ('disapprove', 'Disapprove'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    file_id = fields.Many2one('muk_dms.file', string="File")
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)
    score_list_id = fields.Many2one('iac.score.list', string="Score List")  # 评核名单
    user_score = fields.Float(string="User Score",  digits=(7, 2))# line加总
    user_class=fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ],string="User Class")
    class_approve_log_ids = fields.One2many('iac.class.approve.log','class_supplier_company_id', index=True)

    def button_search_log(self):
        """ SCM/QM 查询评鉴签核历史 """
        # print sys.path
        for class_record in self:
            # for line_obj in score_record.line_ids:
            #     score_record.env['iac.score.part_category.line'].search()
            action = {
                        'name': _('Approval Log'),
                        'view_mode': 'tree',
                        # 'res_model': self._name,
                        'res_model': 'iac.class.approve.log',
                        'type': 'ir.actions.act_window',
                        'view_id': self.env.ref('iac_vendor_evaluation.view_log_signature_class_history_list').id,
                        # 'act_window_id': self.env.ref('iac_vendor_evaluation.action_view_qm_scm_read_score_history').id,
                        'domain': [('class_supplier_company_id', '=', class_record.id)],
                        'res_id': class_record.id
                    }
            return action

    # ning add 新增计算class sc的分数和等级的方法
    def cal_class_supplier_company(self):
        # 获取supplier_company 的最终分数
        self.env.cr.execute("""
                        SELECT
                            sum(COALESCE(weight_score,0) *weight) weight_score
                        FROM
                            iac_score_supplier_company
                        WHERE
                        score_snapshot=%s
                        and supplier_company_id=%s

                                    """, (self.score_snapshot, self.supplier_company_id.id))
        pg_result = self.env.cr.dictfetchone()
        weight_score = pg_result["weight_score"]
        update_vals = {
            "calculate_score": weight_score,
            "user_score": weight_score
        }

        # 根据计算分数计算等级信息
        if weight_score >= 85:
            update_vals["calculate_class"] = "A"
            update_vals["user_class"] = "A"
        elif weight_score >= 70 and weight_score < 85:
            update_vals["calculate_class"] = 'B'
            update_vals["user_class"] = "B"
        elif weight_score >= 60 and weight_score < 70:
            update_vals["calculate_class"] = 'C'
            update_vals["user_class"] = "C"
        else:
            update_vals["calculate_class"] = 'D'
            update_vals["user_class"] = "D"

        # 更新weight数据
        super(IacClassSupplierCompany, self).write(update_vals)

    @api.model
    def create(self,vals):
        result=super(IacClassSupplierCompany,self).create(vals)
        return result

    # 不能注释
    def update_score_data_rec(self):
        """
        提供给外部调用的方法,只能被单挑记录来调用
        :return:
        """
        self._update_class_supplier_company_data()

    # 不能注释
    def _update_class_supplier_company_data(self):
        """
        只能被单一记录对象调用
        更新分数相关的数据
        """
        #获取supplier_company 的最终分数
        self.env.cr.execute("""
            SELECT
                sum(COALESCE(weight_score,0) *weight) weight_score
            FROM
                iac_score_supplier_company
            WHERE
            score_snapshot=%s
            and supplier_company_id=%s

                        """,(self.score_snapshot,self.supplier_company_id.id))
        pg_result = self.env.cr.dictfetchone()
        weight_score=pg_result["weight_score"]
        update_vals={
           # "calculate_score":weight_score
            "user_score": weight_score
        }

        #根据计算分数计算等级信息
        if weight_score >= 85:
           # update_vals["calculate_class"]="A"
            update_vals["user_class"]="A"
        elif weight_score >= 70 and weight_score < 85:
           # update_vals["calculate_class"] = 'B'
            update_vals["user_class"]="B"
        elif weight_score >= 60 and weight_score < 70:
         #   update_vals["calculate_class"] = 'C'
            update_vals["user_class"]="C"
        else:
         #   update_vals["calculate_class"] = 'D'
            update_vals["user_class"]="D"

        #更新weight数据
        super(IacClassSupplierCompany,self).write(update_vals)
        # 非D class直接更新，并且call sap
        if update_vals["user_class"] in ['A', 'B', 'C']:
            # if self.call_sap_change_sc_class(self.supplier_company_id, self.final_class):
            self.state = 'done'
            # 修改SC资料
            self.supplier_company_id.current_class = self.final_class
            self.supplier_company_id.class_date = fields.Date.today()
            self.supplier_company_id.score_snapshot = self.score_snapshot
            # 将该class supplier company下的score数据状态改成done
            for sc_score_id in self.score_supplier_company_ids:
                sc_score_id.state = 'done'
        else:
            super(IacClassSupplierCompany,self).write({"state":"in_review"})


    # @api.multi
    # def write(self, values):
    #     # 记录操作人
    #     if self.env.user.has_group('oscg_vendor.group_scm_controller'):
    #         values['scm_controller_id'] = self.env.user.partner_id.id
    #     if self.env.user.has_group('oscg_vendor.group_qm_leader'):
    #         values['qm_leader_id'] = self.env.user.partner_id.id
    #     result = super(IacClassSupplierCompany, self).write(values)
    #     return result

    # @api.depends('calculate_score')
    # def _compute_calculate_supplier_class(self):
    #     for sc_class_id in self:
    #         result = 'C'
    #         if sc_class_id.calculate_score >= 85:
    #             result = 'A'
    #         elif sc_class_id.calculate_score >= 70 and sc_class_id.calculate_score < 85:
    #             result = 'B'
    #         elif sc_class_id.calculate_score >= 60 and sc_class_id.calculate_score < 70:
    #             result = 'C'
    #         else:
    #             result = 'D'
    #         sc_class_id.calculate_class = result

    # @api.depends('calculate_score')
    # def _compute_final_supplier_class(self):
    #     for sc_class_id in self:
    #         result = 'C'
    #         if sc_class_id.calculate_score >= 85:
    #             result = 'A'
    #         elif sc_class_id.calculate_score >= 70 and sc_class_id.calculate_score < 85:
    #             result = 'B'
    #         elif sc_class_id.calculate_score >= 60 and sc_class_id.calculate_score < 70:
    #             result = 'C'
    #         else:
    #             result = 'D'
    #         sc_class_id.final_class = result
    #         # 非D class直接更新，并且call sap
    #         if result in ['A', 'B', 'C']:
    #             if sc_class_id.call_sap_change_sc_class(
    #                     sc_class_id.supplier_company_id, sc_class_id.final_class):
    #                 sc_class_id.state = 'done'
    #                 # 修改SC资料
    #                 sc_class_id.supplier_company_id.current_class = sc_class_id.final_class
    #                 sc_class_id.supplier_company_id.class_date = fields.Date.today()
    #                 sc_class_id.supplier_company_id.score_snapshot = sc_class_id.score_snapshot
    #                 # 将该class supplier company下的score数据状态改成done
    #                 for sc_score_id in sc_class_id.score_supplier_company_ids:
    #                     sc_score_id.state = 'done'

    # @api.depends('score_supplier_company_ids.weight_score')
    # def _compute_calculate_supplier_score(self):
    #     """根据当前supplier_company_id到iac.score.supplier_company里汇总计算分数"""
    #     for sc_class in self:
    #         sum_score = 0
    #         for sc_site_score in sc_class.score_supplier_company_ids:
    #             sum_score += sc_site_score.weight_score
    #         sc_class.calculate_score = sum_score

    @api.multi
    def button_upload_file(self):
        for pc_class in self:
            action = {
                'name': _('Upload File'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': self._name,  # 跳转模型名称
                'res_id': pc_class.id
            }
            return action

    # 190917 ning 调整    重写的 call_sap_change_sc_class方法
    # 根据传入的flag判断是核准分数还是核准d class '0'表示核准d class '1'表示核准分数
    @api.multi
    def call_sap_change_sc_class_update(self, supplier_company_id, final_class, flag, score_snapshot):
        if flag == '0':
            for line_id in supplier_company_id.line_ids:
                # odoo vendor 005 传参
                vals_005 = {
                    'id': line_id.vendor_id.id,
                    'biz_object_id': line_id.vendor_id.id,
                    'delete_flag': flag
                }
                sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
                # odoo vendor 006 传参
                vals_006 = {
                    "id": line_id.vendor_id.id,
                    "odoo_key": sequence,
                    "biz_object_id": line_id.vendor_id.id,
                    "vendor_code": line_id.vendor_id.vendor_code,
                    "purchase_org": line_id.vendor_id.plant.purchase_org,
                    "current_class": final_class
                }
                try:
                    rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                        'iac.interface.rpc'].invoke_web_call_with_log('ODOO_VENDOR_005', vals_005)
                    if rpc_result:
                        line_id.vendor_id.write({'state': 'deleted'})
                        line_id.vendor_id.vendor_reg_id.with_context({"no_check_short_name": True}).write(
                            {'state': 'deleted'})
                    else:
                        return exception_log[0]['Message']
                    rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                        'iac.interface.rpc'].invoke_web_call_with_log('ODOO_VENDOR_006', vals_006)
                    if not rpc_result:
                        return exception_log[0]['Message']
                except:
                    self.env.cr.rollback()
                    raise UserError(traceback.format_exc())
            # 修改SC资料
            value = {'current_class': final_class,
                     'class_date': datetime.today(),
                     'score_snapshot': score_snapshot}
            supplier_company_id.write(value)
            for line in self.env['iac.score.list'].search([('supplier_company_id', '=', supplier_company_id.id),
                                                           ('score_snapshot', '=', score_snapshot)]):
                line.write({'state': 'done'})

            return True
        if flag == '1':
            if supplier_company_id.current_class == 'D' and final_class != 'D':
                for line_id in supplier_company_id.line_ids:
                    # odoo vendor 005 传参
                    vals_005 = {
                        'id': line_id.vendor_id.id,
                        'biz_object_id': line_id.vendor_id.id,
                        'delete_flag': flag
                    }
                    try:
                        rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                            'iac.interface.rpc'].invoke_web_call_with_log('ODOO_VENDOR_005', vals_005)
                        if rpc_result:
                            line_id.vendor_id.write({'state': 'done'})
                            line_id.vendor_id.vendor_reg_id.with_context({"no_check_short_name": True}).write(
                                {'state': 'done'})
                        else:
                            return exception_log[0]['Message']
                    except:
                        self.env.cr.rollback()
                        raise UserError(traceback.format_exc())
            for line_id in supplier_company_id.line_ids:
                sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
                # odoo vendor 006 传参
                vals_006 = {
                    "id": line_id.vendor_id.id,
                    "odoo_key": sequence,
                    "biz_object_id": line_id.vendor_id.id,
                    "vendor_code": line_id.vendor_id.vendor_code,
                    "purchase_org": line_id.vendor_id.plant.purchase_org,
                    "current_class": final_class
                }
                try:
                    # self.env.savepoint()
                    rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                        'iac.interface.rpc'].invoke_web_call_with_log('ODOO_VENDOR_006', vals_006)
                    if not rpc_result:
                        return exception_log[0]['Message']
                except:
                    self.env.cr.rollback()
                    raise UserError(traceback.format_exc())
            # 修改SC资料
            value = {'current_class': final_class,
                     'class_date': datetime.today(),
                     'score_snapshot': score_snapshot}
            supplier_company_id.write(value)
            for line in self.env['iac.score.list'].search([('supplier_company_id', '=', supplier_company_id.id),
                                                           ('score_snapshot', '=', score_snapshot)]):
                line.write({'state': 'done'})

            return True

    # 注释,重写方法
    # def call_sap_change_sc_class(self, supplier_company_id, current_class):
    #     """
    #     调用sap，修改sc的class，如果current_class为D，则删除vendor
    #     :param object_id:
    #     :param current_class:
    #     :return:
    #     """
    #     # 查找该class_sc_id下SC有效的vendor
    #     process_result=True
    #     sc_ex_list=[]
    #     for line_id in supplier_company_id.line_ids:
    #         #只有done状态的才进行SAP接口调用
    #         if line_id.vendor_id.state == 'done':
    #             continue
    #
    #         #如果是假的接口调用直接返回真的值
    #         if  tools.config.get('dummy_interface',False):
    #            return True
    #
    #         #进行接口调用 ODOO_VENDOR_006 修改supplier company line 对应的vendor 等级信息
    #         sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
    #         biz_object = {
    #             "id": line_id.vendor_id.id,
    #             "odoo_key": sequence,
    #             "biz_object_id": line_id.vendor_id.id,
    #             "vendor_code": line_id.vendor_id.vendor_code,
    #             "purchase_org": line_id.vendor_id.plant.purchase_org,
    #             "current_class": current_class
    #         }
    #         rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
    #             "iac.interface.rpc"].invoke_web_call_with_log(
    #             "ODOO_VENDOR_006", biz_object)
    #
    #         #调用SAP 系统失败的情况下要记录异常日志信息,并跳出当前循环
    #         if rpc_result==False:
    #             sc_line_vals={
    #                 "state":"sap_error",
    #                 "state_msg":exception_log
    #             }
    #             line_id.write(sc_line_vals)
    #             sc_ex_list.append(exception_log)
    #             continue
    #         else:
    #             sc_line_vals={
    #                 "state":"done",
    #                 "state_msg":False
    #             }
    #             line_id.write(sc_line_vals)
    #
    #         #如果当前的supplier company 的等级为D级,那么直接设置vendor 的状态为deleted
    #         #只有D级别的Class 才会使用
    #         if current_class == 'D':
    #             # 删除vendor
    #             biz_param = {
    #                 "id": line_id.vendor_id.id,
    #                 "biz_object_id": line_id.vendor_id.id,
    #                 "vendor_code": line_id.vendor_id.vendor_code,
    #                 "purchase_org": line_id.vendor_id.plant.purchase_org,
    #                 "delete_flag": '0'
    #             }
    #             rpc_result, rpc_json_data, log_line_id, exception_log=self.env["iac.interface.rpc"].invoke_web_call_with_log("ODOO_VENDOR_005", biz_param)
    #             if rpc_result:
    #                 line_id.vendor_id.write({"state":"deleted"})
    #                 line_id.vendor_id.vendor_reg_id.write({"state":"deleted"})
    #                 sc_line_vals={
    #                     "state":"done",
    #                     "state_msg":False
    #                 }
    #                 line_id.write(sc_line_vals)
    #             else:
    #                 sc_line_vals={
    #                     "state":"sap_error",
    #                     "state_msg":exception_log
    #                 }
    #                 line_id.write(sc_line_vals)
    #                 sc_ex_list.append(exception_log)
    #     #如果调用明细条目出现异常的情况下，应该显示异常信息
    #     if len(sc_ex_list)>0:
    #         sc_vals={
    #             "state":"sap_error",
    #             "state_msg":sc_ex_list
    #         }
    #         supplier_company_id.write(sc_vals)
    #         process_result=False
    #     return process_result

class IacClassSupplierCompanyScmController(models.Model):
    _name = 'iac.class.supplier_company.scm_controller'
    _inherit = 'iac.class.supplier_company'
    _table = 'iac_class_supplier_company'

    # @api.multi
    # def action_batch_submit(self):
    #     """
    #     SCM Controller评定class，最终提交
    #     :return:
    #     """
    #     for class_supplier_company_id in self:
    #         if class_supplier_company_id.calculate_class == 'D':
    #             if not class_supplier_company_id.file_id:
    #                 raise UserError(_(u'系统计算Class为D，需上传文件。'))
    #
    #         # SCM评定的各等级class part category 都要QM Leader核准
    #         if class_supplier_company_id.state == 'scoring':
    #             if class_supplier_company_id.calculate_class == 'D':
    #                 class_supplier_company_id.state = 'to approve'
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"提交成功！")
    #         else:
    #             pass
                #return self.env['warning_box'].info(title=u"提示信息", message=u"您已提交过，无需重复提交！")
    #
    def button_download_file(self):
        """
        下载模型中的file_id 对应的文件
        :return:
        """

        return {
            'type': 'ir.actions.act_url',
            'url': self.file_id.link_download,
            'target': 'new',
            }

    @api.multi
    def action_batch_submit(self):
        """
        SCM Controller评定class，最终提交
        :return:
        """
        for class_supplier_company_id in self:
            # if class_supplier_company_id.state != 'in_review':
            #     raise UserError('只可以提交In Review状态的资料')
            if class_supplier_company_id.user_class == 'D':
                if not class_supplier_company_id.file_id:
                    raise UserError(_(u'系统计算Class为D，需上传文件。'))
            if not class_supplier_company_id.scm_memo:
                raise UserError(u'SCM Controller Memo不能为空')
        for class_supplier_company_id in self:
            # SCM评定的各等级class part category 都要QM Leader核准
            # if class_supplier_company_id.state == 'in_review':
            #     if class_supplier_company_id.user_class == 'D':
            class_supplier_company_id.state = 'to approve'
            class_approve_vals = {
                'score_snapshot': class_supplier_company_id.score_snapshot,
                'class_supplier_company_id': class_supplier_company_id.id,
                'user_id': self._uid,
                'approve_role': 'scm_controller',
                'action': 'SCM Controller送签D class',
                'memo': 'scm controller D class送QM leader签核',
                'user_class': class_supplier_company_id.user_class
            }
            self.env['iac.class.approve.log'].create(class_approve_vals)

        return self.env['warning_box'].info(title=u"提示信息", message=u"提交成功！")

    # scm controller d class 退件
    @api.multi
    def action_batch_disapprove(self):
        for class_supplier_company_id in self:
            if not class_supplier_company_id.scm_memo:
                raise UserError(u'SCM Controller Memo不能为空')

        for class_supplier_company_id in self:
            class_supplier_company_id.state = 'scm_ctl_disapproved'
            class_approve_vals = {
                'score_snapshot': class_supplier_company_id.score_snapshot,
                'class_supplier_company_id': class_supplier_company_id.id,
                'user_id': self._uid,
                'approve_role': 'scm_controller',
                'action': 'SCM Controller退件D class',
                'memo': 'scm controller D class退件重评',
                'user_class': class_supplier_company_id.user_class
            }
            self.env['iac.class.approve.log'].create(class_approve_vals)
            score_part_category_objs = self.env['iac.score.part_category'].sudo().search(
                [('score_snapshot', '=', class_supplier_company_id.score_snapshot),
                 ('supplier_company_id', '=', class_supplier_company_id.supplier_company_id.id)])
            for score_part_category in score_part_category_objs:
                # score_part_category.sudo().scm_state = 'disapprove'
                # score_part_category.sudo().qm_state = 'disapprove'
                super(IacScorePartCategory, score_part_category).write(
                    {'scm_state': 'disapprove', 'qm_state': 'disapprove'})
                score_approve_vals = {
                    'score_snapshot': score_part_category.sudo().score_snapshot,
                    'score_part_category_id': score_part_category.sudo().id,
                    'user_id': self._uid,
                    'approve_role': 'scm_controller',
                    'approve_status': 'disapprove',
                    'memo': 'scm controller D class退件重评',
                    'part_category_id': score_part_category.sudo().part_category_id.id,
                    'user_score': score_part_category.sudo().user_score
                }
                self.env['iac.score.approve.log'].create(score_approve_vals)
        return self.env['warning_box'].info(title=u"提示信息", message=u"退件成功！")


class IacClassSupplierCompanyQmLeader(models.Model):
    _name = 'iac.class.supplier_company.qm_leader'
    _inherit = 'iac.class.supplier_company'
    _table = 'iac_class_supplier_company'

    @api.multi
    def action_batch_approve(self):
        """
        QM leader核准class，审核通过
        :return:
        """
        for class_supplier_company_id in self:
            if not class_supplier_company_id.qm_memo:
                raise UserError(u'QM Leader Memo不能为空')

        for class_supplier_company_id in self:
            if class_supplier_company_id.state == 'to approve':
                # call sap
                try:
                    msg = self.env['iac.class.supplier_company'].call_sap_change_sc_class_update(
                        class_supplier_company_id.supplier_company_id, 'D', '0',
                        class_supplier_company_id.score_snapshot)
                    if msg == True:
                    # if self.env['iac.class.supplier_company'].call_sap_change_sc_class_update(
                    #         class_supplier_company_id.supplier_company_id, 'D', '0',
                    #         class_supplier_company_id.score_snapshot):
                        # if super(IacClassSupplierCompanyQmLeader, self).call_sap_change_sc_class(class_supplier_company_id.supplier_company_id, class_supplier_company_id.final_class):
                        # call sap成功后修改class状态和sc资料
                        class_supplier_company_id.state = 'done'
                        class_approve_vals = {
                            'score_snapshot': class_supplier_company_id.score_snapshot,
                            'class_supplier_company_id': class_supplier_company_id.id,
                            'user_id': self._uid,
                            'approve_role': 'qm_leader',
                            'action': 'QM Leader签核D class',
                            'memo': 'QM leader核准D class',
                            'user_class': class_supplier_company_id.user_class
                        }
                        self.env['iac.class.approve.log'].create(class_approve_vals)
                        # # 修改SC资料
                        # value = {'current_class': class_supplier_company_id.final_class,
                        #          'class_date': datetime.today(),
                        #          'score_snapshot': class_supplier_company_id.score_snapshot}
                        # class_supplier_company_id.supplier_company_id.write(value)
                        # else:
                        #     raise UserError('CALL SAP失败，请重新审核！')

                    else:
                        raise UserError(msg)
                except:
                    self.env.cr.rollback()
                    raise UserError(traceback.format_exc())

        return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")

    @api.multi
    def action_batch_disapprove(self):
        """
        QM leader核准class 調整，拒绝
        :return:
        """
        for class_supplier_company_id in self:
            if not class_supplier_company_id.qm_memo:
                raise UserError(u'QM Leader Memo不能为空')

        for class_supplier_company_id in self:
            if class_supplier_company_id.state == 'to approve':
                class_supplier_company_id.state = 'disapprove'
                class_approve_vals = {
                    'score_snapshot': class_supplier_company_id.score_snapshot,
                    'class_supplier_company_id': class_supplier_company_id.id,
                    'user_id': self._uid,
                    'approve_role': 'qm_leader',
                    'action': 'QM Leader拒绝D class',
                    'memo': 'QM leader拒绝D class',
                    'user_class': class_supplier_company_id.user_class
                }
                self.env['iac.class.approve.log'].create(class_approve_vals)

        return self.env['warning_box'].info(title=u"提示信息", message=u"退件成功！")

    @api.multi
    def button_download_file(self):
        """
        下载模型中的file_id 对应的文件
        :return:
        """
        return {
            'type': 'ir.actions.act_url',
            'url': self.file_id.link_download,
            'target': 'new',
        }




            # @api.multi
    # def action_batch_approve(self):
    #     """
    #     QM leader核准class，审核通过
    #     :return:
    #     """
    #     for class_supplier_company_id in self:
    #         if class_supplier_company_id.state == 'to approve':
    #             # call sap
    #             if super(IacClassSupplierCompanyQmLeader, self).call_sap_change_sc_class(class_supplier_company_id.supplier_company_id, class_supplier_company_id.final_class):
    #                 # call sap成功后修改class状态和sc资料
    #                 class_supplier_company_id.state = 'done'
    #                 # 修改SC资料
    #                 value = {'current_class': class_supplier_company_id.final_class,
    #                          'class_date': datetime.today(),
    #                          'score_snapshot': class_supplier_company_id.score_snapshot}
    #                 class_supplier_company_id.supplier_company_id.write(value)
    #
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #             else:
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"CALL SAP失败，请重新审核！")

    # @api.multi
    # def action_batch_disapprove(self):
    #     """
    #     QM leader核准class 調整，拒绝
    #     :return:
    #     """
    #     for class_supplier_company_id in self:
    #         if class_supplier_company_id.state == 'to approve':
    #             class_supplier_company_id.state = 'disapprove'
    #
    #         return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")

class IacClassPartCategory(models.Model):
    """
    材料类别等级表
    由各site的part category score数据汇总而来
    由交易金額大的廠區之SCM controller来处理
    该model
    """
    _name = 'iac.class.part_category'
    _description = "Part Category Class"
    _order = "id desc"

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    score_part_category_ids = fields.One2many('iac.class.score.part_category', 'class_part_category_id', string="Part Category Score")
    class_supplier_company_id = fields.Many2one('iac.class.supplier_company', string="Supplier Company Class")
    #calculate_score = fields.Float(string="Calculate Score", compute="_compute_calculate_part_score", digits=(7, 2), store=True)# 加权分数
    calculate_score = fields.Float(string="Calculate Score",  digits=(7, 2), store=True)# 加权分数
    #calculate_part_class = fields.Selection([
    #    ('A', 'A'),
    #    ('B', 'B'),
    #    ('C', 'C'),
    #    ('D', 'D'),
    #    ('DW', 'DW'),
    #    ], compute="_compute_calculate_part_class", string="Calculate Part Class", store=True)
    calculate_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
        ],  string="Calculate Part Class", store=True)
    final_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ], string="Final Part Class")
    scm_controller_id = fields.Many2one('res.partner', string="SCM Controller", domain="[('supplier','=',False)]")
    scm_partner_id = fields.Many2one('res.partner', string="SCM User", domain="[('in_scm_user_group','=',True)]")
    scm_memo = fields.Text(string="SCM Memo")
    qm_controller_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    qm_leader_id = fields.Many2one('res.partner', string="QM Controller", domain="[('supplier','=',False)]")
    qm_memo = fields.Text(string="QM Memo")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")
    dclass_remark = fields.Text(string="D Class Remark")
    file_id = fields.Many2one('muk_dms.file', string="File")
    dclass_file_id = fields.Many2one('muk_dms.file', string="D Class File")
    plm_number = fields.Integer(string="PLM Number")
    plm_remark = fields.Text(string="PLM Remark")
    state = fields.Selection([
        ('scoring', 'To Judge Class'),# 打分完成，待SCM Controller评级
        ('to approve', 'To Approve'),# 評核結果不管是不是D級，都需QM Leader核准
        ('disapprove', 'Disapprove'),# QM Leader审核不通过
        ('done', 'Done'),# 非D Class评级完成
        ('d class', 'D Class'),# 等待D Class处理
        ('to scm leader approve', 'To SCM Leader Approve'),# SCM Leader审核D Class
        ('to qm controller approve', 'To QM Controller Approve'),# QM Controller审核D Class
        ('to qm leader approve', 'To QM Leader Approve'),# QM Leader审核D Class
        ('d done', 'D Class Done'),# D Class处理完成
    ], string='Status', readonly=True, index=True, copy=False, default='scoring', track_visibility='onchange')
    disapproval_memo = fields.Text(string="Disapproval Memo")
    score_snapshot = fields.Char(string='Score Snapshot', readonly=True)  # 识别快照号，标记使用的哪个材料类别/评分区间/失败成本区间的快照
    score_list_id = fields.Many2one('iac.score.list', string="Score List")  # 评核名单
    vendor_codes = fields.Char(string="Vendor Codes", compute='_taken_vendor_codes')# SC 中参与评核的Vendor Code，多个Vendor Code用逗号隔开
    user_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ], string="User Part Class", store=True)
    user_score = fields.Float(string="Calculate Score",  digits=(7, 2), store=True)

    # 190925 ning add 更新class part category的分数和等级
    def cal_class_part_category(self):
        # 获取权重分数汇总,不分厂区
        self.env.cr.execute("""
                        SELECT
                            COALESCE(SUM (weight_score),0) weight_score
                        FROM
                            iac_score_part_category
                        WHERE
                            supplier_company_id=%s
                            and part_category_id=%s
                            and score_snapshot=%s
                                    """, (self.supplier_company_id.id, self.part_category_id.id, self.score_snapshot))
        pg_result = self.env.cr.dictfetchone()
        weight_score = pg_result["weight_score"]
        update_vals = {
            "calculate_score": weight_score,
            "user_score": weight_score
        }

        # 计算得出part_category_class
        if weight_score >= 85:
            update_vals["calculate_part_class"] = 'A'
            update_vals["user_part_class"] = 'A'
        elif weight_score >= 70 and weight_score < 85:
            update_vals["calculate_part_class"] = 'B'
            update_vals["user_part_class"] = 'B'
        elif weight_score >= 60 and weight_score < 70:
            update_vals["calculate_part_class"] = 'C'
            update_vals["user_part_class"] = 'C'
        else:
            update_vals["calculate_part_class"] = 'D'
            update_vals["user_part_class"] = 'D'
        super(IacClassPartCategory, self).write(update_vals)

    @api.depends('supplier_company_id')
    def _taken_vendor_codes(self):
        for v in self:
            domain=[('supplier_company_id','=',v.supplier_company_id.id)]
            vendor_list=self.env["iac.vendor"].search(domain)
            vendor_codes = []
            for vendor_rec in vendor_list:
                vendor_codes.append(vendor_rec.vendor_code)
            v.vendor_codes = ','.join(vendor_codes)

    # 不能注释
    def update_class_part_category_data_ref(self,i,lenth):
        """
        提供外部访问,只能被单笔class.part.category记录调用
        :return:
        """
        self._update_class_part_category_data_ref(i,lenth)
    # 不能注释
    def _update_class_part_category_data_ref(self,i,lenth):
        """
        只能由单笔class.part.category记录调用,计算级别和分数信息
        只能在 iac.score.part_category 的全部厂区评分完成的情况下才能调用这个方法

        更新分数相关的数据
        """

        #获取权重分数汇总,不分厂区
        self.env.cr.execute("""
            SELECT
                COALESCE(SUM (weight_score),0) weight_score
            FROM
                iac_score_part_category
            WHERE
                supplier_company_id=%s
                and part_category_id=%s
                and score_snapshot=%s
                        """,(self.supplier_company_id.id,self.part_category_id.id,self.score_snapshot))
        pg_result = self.env.cr.dictfetchone()
        weight_score=pg_result["weight_score"]
        update_vals={
            "user_score":weight_score
        }


        # 计算得出part_category_class
        if weight_score >= 85:
            update_vals["user_part_class"] = 'A'
        elif weight_score >= 70 and weight_score < 85:
            update_vals["user_part_class"] = 'B'
        elif weight_score >= 60 and weight_score < 70:
            update_vals["user_part_class"] = 'C'
        else:
            update_vals["user_part_class"] = 'D'
        super(IacClassPartCategory,self).write(update_vals)

        #在当前公司的全部class_part_category 都评分完成的情况下,开始级联更新 score_supplier_company

        #被调用的函数内部进行判断
        self.env["iac.score.supplier_company"].update_score_company_data_ref(self.sudo().supplier_company_id.id,self.sudo().score_snapshot,i,lenth)



    @api.model
    def create(self,vals):
        result=super(IacClassPartCategory,self).create(vals)

        return result

    # @api.multi
    # def write(self, values):
    #     # 记录操作人
    #     if self.env.user.has_group('oscg_vendor.group_scm_controller'):
    #         values['scm_controller_id'] = self.env.user.partner_id.id
    #     if self.env.user.has_group('oscg_vendor.group_scm_user'):
    #         values['scm_partner_id'] = self.env.user.partner_id.id
    #     if self.env.user.has_group('oscg_vendor.group_qm_controller'):
    #         values['qm_controller_id'] = self.env.user.partner_id.id
    #     if self.env.user.has_group('oscg_vendor.group_qm_leader'):
    #         values['qm_leader_id'] = self.env.user.partner_id.id
    #
    #     #增加校验,打分完成和supplier_company 风险等级评定之后才能进行 材料等级评定
    #
    #     if "final_part_class" in values:
    #         for class_line in self:
    #             domain=[('supplier_company_id','=',class_line.supplier_company_id.id),('score_snapshot','=',class_line.score_snapshot)]
    #             domain+=[('state','=','draft')]
    #             sc_risk_rec=self.env["iac.supplier.company.risk"].sudo().search(domain)
    #
    #             domain=[('supplier_company_id','=',class_line.supplier_company_id.id),('score_snapshot','=',class_line.score_snapshot)]
    #             domain+=[('state','=','scoring')]
    #             score_part_category_rec=self.env["iac.score.part_category"].sudo().search(domain)
    #             if sc_risk_rec.exists() or score_part_category_rec.exists():
    #                 raise UserError("必须先完成打分和Supplier Company 风险等级评定后才可以评定材料等级")
    #     result = super(IacClassPartCategory, self).write(values)
    #     return result

    # @api.depends('calculate_score')
    # def _compute_calculate_part_class(self):
    #     for score in self:
    #         result = 'C'
    #         if score.calculate_score >= 85:
    #             result = 'A'
    #         elif score.calculate_score >= 70 and score.calculate_score < 85:
    #             result = 'B'
    #         elif score.calculate_score >= 60 and score.calculate_score < 70:
    #             result = 'C'
    #         else:
    #             result = 'D'
    #
    #         score.calculate_part_class = result

    # @api.depends('score_part_category_ids.weight_score')
    # def _compute_calculate_part_score(self):
    #     """根据当前supplier_company_id、part_category_id到iac.score.part_category里汇总计算分数
    #         各site对part category打分，各site汇总的part category的分数就是class级别的score
    #     """
    #     for pc_class in self:
    #         sum_score = 0
    #         for part_category_score in pc_class.score_part_category_ids:
    #             sum_score += part_category_score.weight_score
    #         pc_class.calculate_score = sum_score

    @api.multi
    def button_upload_file(self):
        for pc_class in self:
            action = {
                'name': _('Upload File'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': self._name,  # 跳转模型名称
                'res_id': pc_class.id
            }
            return action

class IacClassPartCategoryScmController(models.Model):
    """SCM Controller 评定 Class"""
    _name = 'iac.class.part_category.scm_controller'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

    # @api.multi
    # def action_batch_submit(self):
    #     """
    #     SCM Controller评定class，最终提交
    #     :return:
    #     """
    #     supplier_company_ids=[]
    #     score_snapshot=''
    #     for class_part_category_id in self:
    #         if not class_part_category_id.final_part_class:
    #             raise UserError(_(u'请选择最终确认Class。'))
    #         if class_part_category_id.calculate_part_class == 'D' and class_part_category_id.final_part_class != 'D':
    #             if not class_part_category_id.file_id:
    #                 raise UserError(_(u'系统计算Class为D，但是最终确认Class不为D，需上传文件。'))
    #         supplier_company_ids.append(class_part_category_id.supplier_company_id.id)
    #         score_snapshot=class_part_category_id.score_snapshot
    #         # SCM评定的各等级class part category 都要QM Leader核准
    #         if class_part_category_id.state == 'scoring':
    #             if class_part_category_id.calculate_part_class == 'D' and class_part_category_id.final_part_class != 'D':
    #                 class_part_category_id.state = 'to approve'
    #             elif class_part_category_id.final_part_class == 'D':
    #                 class_part_category_id.state = 'd class'
    #             else:
    #                 class_part_category_id.state="done"
    #             # 将该class part category下的score数据状态改成done
    #             for score_part_category_id in class_part_category_id.score_part_category_ids:
    #                 score_part_category_id.state="done"
    #                 #part_score header 状态为done 的情况下 part_score_line状态也修改为done
    #                 for scoe_part_category_line_id in score_part_category_id.line_ids:
    #                     scoe_part_category_line_id.state="done"
    #             self.env.cr.commit()
    #         elif class_part_category_id.state == 'disapprove':
    #             class_part_category_id.state = 'to approve'
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"提交成功！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已提交过，无需重复提交！")
    #     #更新分厂区的分数和权重信息
    #     supplier_company_ids=list(set(supplier_company_ids))
    #     for supplier_company_id in supplier_company_ids:
    #         self.env["iac.score.supplier_company"].update_score_company_data_ref(supplier_company_id,score_snapshot)
    #     return self.env['warning_box'].info(title=u"提示信息", message=u"提交成功！")


class IacClassPartCategoryQmLeader(models.Model):
    _name = 'iac.class.part_category.qm_leader'
    _inherit = 'iac.class.part_category'
    _table = 'iac_class_part_category'

    # def button_download_file(self):
    #     """
    #     下载模型中的file_id 对应的文件
    #     :return:
    #     """

        # return {
        #     'type': 'ir.actions.act_url',
        #     'url': self.file_id.link_download,
        #     'target': 'new',
        #     }
        #
        # pass

    # @api.multi
    # def action_batch_approve(self):
    #     """
    #     QM leader核准class，审核通过
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to approve':
    #             if class_part_category_id.final_part_class != 'D':
    #                 class_part_category_id.state = 'done'
    #             else:
    #                 class_part_category_id.state = 'd class'
    #
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已审核过，无需重复审核！")
    #
    # @api.multi
    # def action_batch_disapprove(self):
    #     """
    #     QM leader核准class 調整，拒绝
    #     :return:
    #     """
    #     for class_part_category_id in self:
    #         if class_part_category_id.state == 'to approve':
    #             class_part_category_id.state = 'disapprove'
    #
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已审核过，无需重复审核！")

class IacSupplierCompanyScoreGenerate(models.Model):
    """手动产生评核名单的继承SC model"""
    _name = "iac.generate.supplier.company"
    _inherit = 'iac.supplier.company'
    _table = 'iac_supplier_company'

    @api.multi
    def button_batch_gen_score_list(self):
        """
        手动产生评核名单
        :return:
        """
        score_snapshot = fields.Date.today()  # 快照号
        for supplier_company_id in self:
            domain = [('id', '=', supplier_company_id.id)]
            score_list = self.env['task.vendor.score'].gen_score_list(score_snapshot,domain,'manual')
            if score_list:
                self.env['task.vendor.score'].backup_score_data(score_snapshot)
            for score_list_id in score_list:
                self.env['task.vendor.score'].calc_vendor_score(score_list_id,score_snapshot,'manual')
            if score_list:
                self.env['task.vendor.score'].create_class_part_data(score_snapshot)
                self.env['task.vendor.score'].create_class_company_data(score_snapshot)
                self.env['task.vendor.score'].cal_sc_class_score(score_list,score_snapshot)
                self.env['task.vendor.score'].update_supplier_company_score(score_list,score_snapshot)

            #计算风险等级
            score_list_ids=[]
            for score_list_id in score_list:
                score_list_ids.append(score_list_id.id)
                score_list_id.write({"score_type":"manual"})
            self.env["task.vendor.score"].calcu_supplier_company_risk(score_list_ids,score_snapshot)
            # 写入log表
            score_list_ids = []
            for score_list_id in score_list:
                score_list_ids.append(score_list_id.id)
            self.env["task.vendor.score"].insert_score_approve_log(score_list_ids, score_snapshot, 'system', 'initial',
                                                                   '系统初始化评分数据')
            self.env["task.vendor.score"].insert_class_approve_log(score_list_ids, score_snapshot, 'system', '产生评鉴资料',
                                                                   '系统初始化评分数据')

        return self.env['warning_box'].info(title=u"提示信息", message=u"手动产生评核名单操作完成，共产生 %s 个评核名单。" % len(score_list))

class IacSupplierCompanyScoreDClassReturn(models.Model):
    """
    SCM Controller申请d class 返回
    """
    _name = "iac.dclass_return.supplier.company"
    _inherit = 'iac.supplier.company'
    _table = 'iac_supplier_company'

    # @api.multi
    # def button_apply(self):
    #     """
    #     SCM Controller申请d class 返回
    #     :return:
    #     """
    #     for sc_id in self:
    #         # 已经申请过的不再创建
    #         dclass_return_id = self.env['iac.dclass.return'].search([('supplier_company_id', '=', sc_id.id),
    #                                               ('vendor_id', '=', self.env.context.get('dclass_vendor_id')),
    #                                                                  ('state', '!=', 'cancel')], limit=1)
    #         if dclass_return_id:
    #             if dclass_return_id.state == 'to approve':
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"您的申请正在审核！")
    #             elif dclass_return_id.state == 'done':
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"您的申请已经核准通过，无需重复申请！")
    #         else:
    #             # 产生iac.dclass.return数据
    #             dclass_vals = {
    #                 'supplier_company_id': sc_id.id,
    #                 'vendor_id': self.env.context.get('dclass_vendor_id')
    #             }
    #             dclass_return_id = self.env['iac.dclass.return'].create(dclass_vals)
    #
    #         action = {
    #             'name': _('D Class Return'),
    #             'type': 'ir.actions.act_window',
    #             'view_type': 'form',
    #             'view_mode': 'form',
    #             'res_model': 'iac.dclass.return',  # 跳转模型名称
    #             'res_id': dclass_return_id.id  # 跳转模型id
    #         }
    #         return action

class IacScoreDClassReturn(models.Model):
    """
    SCM Controller上传文件后提交qm leader审核
    """
    _name = "iac.dclass.return"

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company", required=True, readonly=True)
    vendor_id = fields.Many2one('iac.vendor', string='Vendor Code', required=True, readonly=True)
    dclass_file_id = fields.Many2one('muk_dms.file', string="File")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to approve', 'To Approve'),
        ('disapprove', 'Disapprove'),
        ('cancel', 'Cancel'),
        ('done', 'Done'),
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    # @api.multi
    # def button_submit(self):
    #     """
    #     SCM Controller提交qm leader审核
    #     :return:
    #     """
    #     for dclass_id in self:
    #         if not dclass_id.dclass_file_id:
    #             raise UserError(_(u'请上传文档！'))
    #         if dclass_id.state in ['draft', 'disapprove']:
    #             dclass_id.state = 'to approve'
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"提交完成！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已提交过，无需重复提交！")
    #
    # @api.multi
    # def button_cancel(self):
    #     for dclass_id in self:
    #         if dclass_id.state in ['draft', 'disapprove']:
    #             dclass_id.state = 'cancel'

class IacDClassReturnQmLeader(models.Model):
    """d class返回的继承SC model，scm controller通过此model上传file，并提交给qm leader审核"""
    _name = "iac.dclass.return.qm_leader"
    _inherit = 'iac.dclass.return'
    _table = 'iac_dclass_return'

    # def button_download_file(self):
    #     """
    #     下载模型中的file_id 对应的文件
    #     :return:
    #     """
    #
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': self.dclass_file_id.link_download,
    #         'target': 'new',
    #         }
    #
    #
    # @api.multi
    # def action_batch_approve(self):
    #     """
    #     QM leader核准d class return，审核通过
    #     :return:
    #     """
    #     for dclass_id in self:
    #         if dclass_id.state == 'to approve':
    #             # call sap通知sap 该SC Class变成C，vendor的state从delete变成done
    #             if self.call_sap_change_vendor_class(dclass_id.vendor_id, 'C') and self.call_sap_change_vendor_state(dclass_id.vendor_id, 1):
    #                 dclass_id.supplier_company_id.write({'current_class': 'C', 'class_date': datetime.today()})
    #                 dclass_id.vendor_id.state = 'done'
    #                 dclass_id.vendor_id.vendor_reg_id.state = 'done'
    #                 dclass_id.state = 'done'
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #             else:
    #                 return self.env['warning_box'].info(title=u"提示信息", message=u"CALL SAP失败，请重新审核！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已审核过，无需重复审核！")
    #
    # @api.multi
    # def action_batch_disapprove(self):
    #     """
    #     QM leader核准d class return，拒绝
    #     :return:
    #     """
    #     for dclass_id in self:
    #         if dclass_id.state == 'to approve':
    #             dclass_id.state = 'disapprove'
    #
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"审核完成！")
    #         else:
    #             return self.env['warning_box'].info(title=u"提示信息", message=u"您已审核过，无需重复审核！")

    # def call_sap_change_vendor_class(self, vendor_id, current_class):
    #     """
    #     call sap 更新SAP中供应商等级，如果current class为D，则调用ODOO_VENDOR_005删除该sc下所有vendor
    #     :param vendor_id:
    #     :param current_class:
    #     :return:
    #     """
    #     try:
    #         if not tools.config.get('dummy_interface',False):
    #             # 调用SAP接口修改vendor状态
    #             sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
    #             biz_object = {
    #                 "id": vendor_id.id,
    #                 "odoo_key": sequence,
    #                 "biz_object_id": vendor_id.id,
    #                 "vendor_code": vendor_id.vendor_code,
    #                 "purchase_org": vendor_id.plant.purchase_org,
    #                 "current_class": current_class
    #             }
    #             rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
    #                 "iac.interface.rpc"].invoke_web_call_with_log(
    #                 "ODOO_VENDOR_006", biz_object)
    #         else:
    #             rpc_result = True
    #         if rpc_result:
    #             return True
    #         else:
    #             return False
    #     except:
    #         traceback.print_exc()
    #         return False
    #
    # def call_sap_change_vendor_state(self, vendor_id, state):
    #     """
    #     修改vendor的state
    #     :param vendor_id:
    #     :param state:
    #     :return:
    #     """
    #     try:
    #         if not tools.config.get('dummy_interface',False):
    #             # 调用SAP接口
    #             biz_object = {
    #                 "id": vendor_id.id,
    #                 "biz_object_id": vendor_id.id,
    #                 "vendor_code": vendor_id.vendor_code,
    #                 "purchase_org": vendor_id.plant.plant_code,
    #                 "delete_flag": state
    #             }
    #             rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
    #                 "iac.interface.rpc"].invoke_web_call_with_log(
    #                 "ODOO_VENDOR_005", biz_object)
    #         else:
    #             rpc_result = True
    #         if rpc_result:
    #             return True
    #         else:
    #             return False
    #     except:
    #         traceback.print_exc()
    #         return False


class IacScoreExculdePlant(models.Model):
    """ 评鉴supplier company排除表，此表中SC排除by site评核 """

    _name = "iac.score.exclude.plant"
    _table = "iac_score_exclude_plant"
    _order = 'id desc'
    supplier_company_id = fields.Many2one('iac.supplier.company', string=u'Supplier company', index=True)
    plant_id = fields.Many2one('pur.org.data', string=u'Plant', index=True)
    active = fields.Boolean('Active', default=True,
        help="If unchecked, it will allow you to hide the definition without removing it.")
    memo = fields.Text(string=u'Memo')


class IacScoreApproveLog(models.Model):
    """ 分数签核历史记录表 """
    _name = "iac.score.approve.log"
    _table = "iac_score_approve_log"
    _order = 'id desc'

    score_snapshot = fields.Char(string='Score Snapshot')
    score_part_category_id = fields.Many2one('iac.score.part_category', string=u'Score part category id', index=True)
    user_id = fields.Many2one('res.users', string=u'user id', index=True)
    approve_role = fields.Selection([("qm_controller", u"QM_CONTROLLER"),
                              ("scm_controller", u"SCM_CONTROLLER"),
                              ("qm_leader", u"QM_LEADER"),
                              ("scm_leader", u"SCM_LEADER"),
                              ("system", u"SYSTEM")], string=u"签核者角色")
    approve_status = fields.Selection([("approve", u"APPROVE"),
                                     ("disapprove", u"DISAPPROVE"),
                                     ("initial", u"INITIAL")], string=u"签核状态")
    memo = fields.Text(string=u'备注')
    part_category_id = fields.Many2one('iac.part.category',string='part_category')
    calculate_score = fields.Float(string='Calculate Score',related='score_part_category_id.class_part_category_id.calculate_score')
    user_score = fields.Float(string='User Score', digits=(7, 2), store=True)


class IacClassApproveLog(models.Model):
    """ 等级签核历史记录表 """
    _name = "iac.class.approve.log"
    _table = "iac_class_approve_log"
    _order = 'id desc'

    score_snapshot = fields.Char(string='Score Snapshot')
    class_supplier_company_id = fields.Many2one('iac.class.supplier_company', string=u'class supplier_company', index=True)
    user_id = fields.Many2one('res.users', string=u'user id', index=True)
    approve_role = fields.Selection([("system", u"SYSTEM"),
                                     ("qm_controller", u"QM_CONTROLLER"),
                                     ("scm_controller", u"SCM_CONTROLLER"),
                                     ("qm_leader", u"QM_LEADER"),
                                     ("scm_leader", u"SCM_LEADER")], string=u"签核者角色")
    action = fields.Selection([("产生评鉴资料", u"产生评鉴资料"),
                               ('SCM/QM Leader核准后重新计算class',u'SCM/QM Leader核准后重新计算class'),
                               ("SCM Controller送签D class", u"SCM Controller送签D class"),
                               ("SCM Controller退件D class", u"SCM Controller退件D class"),
                               ("QM Leader签核D class", u"QM Leader签核D class"),
                               ("QM Leader拒绝D class", u"QM Leader拒绝D class")], string=u"签核环节")
    memo = fields.Text(string=u'备注')
    calculate_class = fields.Selection(string='Calculate Class',related='class_supplier_company_id.calculate_class')
    user_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ], string="User Class")


class QRQCDataForScoring(models.Model):

    # QRQC报表导入的资料，每个月前5天刷新资料

    _name = 'qrqc.data.for.scoring.vs'
    _table = 'qrqc_data_for_scoring_vs'

    plant = fields.Char(string='Plant')
    plant_id = fields.Many2one('pur.org.data',string='plant ID')
    vendorcode = fields.Char(string='Vendor code')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor ID')
    qrqcno = fields.Char(string='QRQC no')
    operatedate = fields.Date(string='Operation date')
    badefnumber = fields.Char(string='Eform number')

class FailCostForScoring(models.Model):

    # 客户求偿单导入的资料，每个月前5天刷新资料

    _name = 'fail.cost.for.scoring.vs'
    _table = 'fail_cost_for_scoring_vs'

    plant = fields.Char(string='Plant')
    plant_id = fields.Many2one('pur.org.data',string='plant ID')
    vendorcode = fields.Char(string='Vendor code')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor ID')
    realpay = fields.Float(string='Fail cost amount')
    appdate = fields.Date(string='Operation date')


# class IacScorePartCategoryScmQm(models.Model):
#     _inherit = 'iac.score.part_category'
#     _name = 'iac.score.part_category.scm.qm'
#     _table = 'iac_score_part_category'