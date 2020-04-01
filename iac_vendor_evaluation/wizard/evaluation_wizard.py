# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class IacVendorScoreSetUserWizard(models.TransientModel):
    """指派评核人员向导"""
    _name = 'iac.vendor.score.setuser.wizard'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    only_unset = fields.Boolean(string=u"仅仅显示还未指定评分User的记录", default=False)

    @api.multi
    def search_vendor_score_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'scoring')]
            if wizard.plant_id:
                domain += [('plant_id', '=', wizard.plant_id.id)]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.only_unset:
                scm_controller_group = self.env.ref('oscg_vendor.group_scm_controller')
                qm_controller_group = self.env.ref('oscg_vendor.group_qm_controller')
                if self.env.user.id in scm_controller_group.users.ids:
                    domain += [('scm_partner_id', '=', False)]# SCM Controller用户组时的条件
                if self.env.user.id in qm_controller_group.users.ids:
                    domain += [('qm_partner_id', '=', False)]# QM Controller用户组时的条件

            result = self.env['iac.score.part_category'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category Score List'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'iac.score.part_category',
            'view_id': self.env.ref('iac_vendor_evaluation.view_score_part_category_list').id,
        }
        return action

class IacVendorScoreUserScoringWizard(models.TransientModel):
    """评核人员打分向导"""
    _name = 'iac.vendor.score.user_scoring.wizard'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")

    @api.multi
    def search_vendor_score_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', 'in', ['scoring','to approve'])]
            if wizard.plant_id:
                domain += [('plant_id', '=', wizard.plant_id.id)]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]

            result = self.env['iac.score.part_category'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category Score List'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'iac.score.part_category',
            'view_id': self.env.ref('iac_vendor_evaluation.view_user_scoring_part_category_list').id,
            'target': 'current',
        }
        return action

class IacVendorScoreSCMPartCategoryClassWizard(models.TransientModel):
    """SCM controller 評定part category class"""
    _name = 'iac.vendor.score.scm_pc_class.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    calculate_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ], string="Calculate Part Class")

    @api.multi
    def search_vendor_score_part_category_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', 'in', ('scoring', 'disapprove','to approve','done'))]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.calculate_part_class:
                domain += [('calculate_part_class', '=', wizard.calculate_part_class)]

            result = self.env['iac.class.part_category.scm_controller'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.scm_controller'
        }
        return action

class IacVendorScoreQMApprovePartClassWizard(models.TransientModel):
    """QM leader核准part class 调整"""
    _name = 'iac.vendor.score.qm_approve_pc_class.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    final_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('DW', 'DW'),
    ], string="Final Part Class")

    @api.multi
    def search_vendor_score_part_category_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', 'in', ['done','to approve']),('calculate_part_class','=','D'),('final_part_class','=','C')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.final_part_class:
                domain += [('final_part_class', '=', wizard.final_part_class)]

            result = self.env['iac.class.part_category.qm_leader'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.qm_leader'
        }
        return action

class IacVendorScoreSCMSCClassWizard(models.TransientModel):
    """SCM controller 确认supplier company class"""
    _name = 'iac.vendor.score.scm_sc_class.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    calculate_class = fields.Char(string="User Class", default='D')

    @api.multi
    def search_supplier_company_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', 'in', ('disapprove','in_review'))]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.calculate_class:
                domain += [('user_class', '=', wizard.calculate_class)]

            result = self.env['iac.class.supplier_company.scm_controller'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Supplier Company Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.supplier_company.scm_controller'
        }
        return action

class IacVendorScoreQMApproveSCClassWizard(models.TransientModel):
    """QM leader核准SC class 调整"""
    _name = 'iac.vendor.score.qm_approve_sc_class.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    final_class = fields.Char(string="User Class", default='D', readonly=True)

    @api.multi
    def search_supplier_company_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'to approve')]
            # domain=[]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.final_class:
                domain += [('user_class', '=', wizard.final_class)]

            result = self.env['iac.class.supplier_company.qm_leader'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.supplier_company.qm_leader'
        }
        return action

class IacVendorScoreGenScoreListWizard(models.TransientModel):
    """手动产生评核名单"""
    _name = 'iac.vendor.score.gen_score_list.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company*")
    final_part_class = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ], string="Current Class")
    qvl_date = fields.Datetime(string="QVL Date")

    @api.multi
    def search_supplier_company_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = []
            if wizard.supplier_company_id:
                domain += [('id', '=', wizard.supplier_company_id.id)]
            if wizard.final_part_class:
                domain += [('current_class', '=', wizard.final_part_class)]
            # if wizard.qvl_date:
            #     domain += [('class_date', '>=', wizard.qvl_date)]

            result = self.env['iac.generate.supplier.company'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Supplier Company Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.generate.supplier.company'
        }
        return action

class IacVendorScoreScmControllerDClassReturnWizard(models.TransientModel):
    """SCM Controller申请D Class返回
    根据Vendor Code查找D Class SC，上傳文檔，提交給QM Leader核准
    """
    _name = 'iac.dclass.return.wizard'

    vendor_id = fields.Many2one('iac.vendor', string='Vendor Code', required=True)
    final_class = fields.Char(string="Final Class", default='D', readonly=True)

    @api.multi
    def search_supplier_company_list(self):
        self.ensure_one()
        for wizard in self:
            if wizard.vendor_id:
                sql = """
                        select a.id 
                        from iac_supplier_company a,
                             iac_supplier_company_line b,
                             iac_vendor c
                        where a.id = b.supplier_company_id
                        and b.vendor_id = c.id
                        and a.current_class = 'D'
                        and c.vendor_code = %s
                                """
                self.env.cr.execute(sql, (wizard.vendor_id.vendor_code,))
                result = self.env.cr.fetchone()
                if result:
                    action = {
                        'name': _('D Class Return'),
                        'type': 'ir.actions.act_window',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'iac.dclass_return.supplier.company',  # 跳转模型名称
                        'res_id': result[0],  # 跳转模型id
                        'context': {'dclass_vendor_id': wizard.vendor_id.id}
                    }
                    return action
                else:
                    return self.env['warning_box'].info(title=u"提示信息", message=u"未找到符合條件的數據！")