# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class IacVendorScoreScmUserDClassWizard(models.TransientModel):
    """D class处理
       由SCM User来选择有特採放行，可採購/不能建BOM(PNRF),不可採購/不可建BOM(CEO零件停產執行單)三種方式
       """
    _name = 'iac.vendor.score.d_class.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    final_part_class = fields.Char(string=u"最终评定 D Class", readonly=True)

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'd class')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            result = self.env['iac.dclass.part_category.scm_user'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.dclass.part_category.scm_user'
        }
        return action

class IacVendorScoreScmControllerDClassApproveWizard(models.TransientModel):
    """SCM Controller核准D Class处理"""
    _name = 'iac.vendor.score.scm_controller.d_class_approval.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'to scm controller approve')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.dclass_type:
                domain += [('dclass_type', '=', wizard.dclass_type)]

            result = self.env['iac.class.part_category.scm_controller'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.scm_controller'
        }
        return action

class IacVendorScoreScmLeaderDClassApproveWizard(models.TransientModel):
    """SCM Leader核准D Class处理"""
    _name = 'iac.vendor.score.scm_leader.d_class_approval.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'to scm leader approve')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.dclass_type:
                domain += [('dclass_type', '=', wizard.dclass_type)]

            result = self.env['iac.class.part_category.scm_leader'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.scm_leader'
        }
        return action

class IacVendorScoreQmControllerDClassApproveWizard(models.TransientModel):
    """QM Controller核准D Class处理"""
    _name = 'iac.vendor.score.qm_controller.d_class_approval.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'to qm controller approve')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.dclass_type:
                domain += [('dclass_type', '=', wizard.dclass_type)]

            result = self.env['iac.class.part_category.qm_controller'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.qm_controller'
        }
        return action

class IacVendorScoreQmLeaderDClassApproveWizard(models.TransientModel):
    """QM Leader核准D class 处理方式"""
    _name = 'iac.vendor.score.qm_leader.d_class_approval.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'to qm leader approve')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.dclass_type:
                domain += [('dclass_type', '=', wizard.dclass_type)]

            result = self.env['iac.class.part_category.qm_leader'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category.qm_leader'
        }
        return action

class IacVendorScoreInputPLMNumberWizard(models.TransientModel):
    """輸入PLM申請單號"""
    _name = 'iac.vendor.score.input_plm_number.wizard'

    supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    part_category_id = fields.Many2one('iac.part.category', string="Part Category")
    dclass_type = fields.Selection([
        ('special.release', u'特採放行'),
        ('can.buy', u'可採購/不能建BOM(PNRF)'),
        ('cannot.buy', u'不可採購/不能建BOM (CEO零件停產執行單)')
    ], string=u"处理方式")

    @api.multi
    def search_part_category_class_list(self):
        self.ensure_one()
        result = []
        for wizard in self:
            domain = [('state', '=', 'd done')]
            if wizard.supplier_company_id:
                domain += [('supplier_company_id', '=', wizard.supplier_company_id.id)]
            if wizard.part_category_id:
                domain += [('part_category_id', '=', wizard.part_category_id.id)]
            if wizard.dclass_type:
                domain += [('dclass_type', '=', wizard.dclass_type)]

            result = self.env['iac.class.part_category'].search(domain)

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': _('Part Category D Class List'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'iac.class.part_category'
        }
        return action