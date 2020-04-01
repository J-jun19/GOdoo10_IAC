# -*- coding: utf-8 -*-

from odoo import models, fields,api
from odoo.exceptions import UserError
from datetime import datetime,timedelta

class IacScoreListInherit(models.Model):
    _name = 'iac.score.list.inherit'
    _inherit = 'iac.score.list'
    _table = 'iac_score_list'

    @api.multi
    def delete_supplier_company(self):
        for item in self:
            score_list_objs = self.env['iac.score.list'].search([
                ('supplier_company_id','=',item['supplier_company_id'].id),
                ('score_snapshot','=',item['score_snapshot']),('id','!=',item['id'])])
            self.env.cr.execute("""delete from iac_score_part_category_line where score_list_id=%s""", (item['id'],))
            self.env.cr.execute("""delete from iac_score_part_category where score_list_id=%s""", (item['id'],))
            self.env.cr.execute("""delete from iac_score_supplier_company where score_list_id=%s""", (item['id'],))
            self.env.cr.execute("""delete from iac_score_list where id=%s""", (item['id'],))
            if len(score_list_objs) == 0:
                self.env.cr.execute("""delete from iac_class_part_category where 
                                                          supplier_company_id=%s and score_snapshot=%s""",
                                       (item['supplier_company_id'].id,item['score_snapshot']))
                self.env.cr.execute("""delete from iac_class_supplier_company where 
                                                                          supplier_company_id=%s and score_snapshot=%s""",
                                    (item['supplier_company_id'].id, item['score_snapshot']))
                self.env.cr.execute("""delete from iac_supplier_company_risk where 
                                                                                          supplier_company_id=%s and score_snapshot=%s""",
                                    (item['supplier_company_id'].id, item['score_snapshot']))
            else:
                #重算sc的分数和等级
                self.env['task.vendor.score'].create_class_part_data(item['score_snapshot'])
                self.env['task.vendor.score'].create_class_company_data(item['score_snapshot'])
                self.env['task.vendor.score'].cal_sc_class_score(score_list_objs, item['score_snapshot'])
                self.env['task.vendor.score'].update_supplier_company_score(score_list_objs, item['score_snapshot'])
                self.env["task.vendor.score"].calcu_supplier_company_risk(score_list_objs, item['score_snapshot'])
            vals = {
                'plant_id':item['plant_id'].id,
                'supplier_company_id':item['supplier_company_id'].id
            }
            self.env['iac.supplier.company.delete.log'].create(vals)

        return self.env['warning_box'].info(title=u"提示信息",message=u"当前SC已删除")


class IacSupplierCompanyDeletelog(models.Model):
    _name = 'iac.supplier.company.delete.log'

    plant_id = fields.Many2one('pur.org.data', string='Plant')
    supplier_company_id = fields.Many2one('iac.supplier.company', string='Supplier Company')


class IacSupplierCompanyDeleteWizard(models.TransientModel):

    _name = 'iac.supplier.company.delete.wizard'

    plant_id = fields.Many2one('pur.org.data',string='Plant')
    supplier_company_id = fields.Many2one('iac.supplier.company',string='Supplier Company')
    date_begin = fields.Date('Score list create date from')
    date_end = fields.Date('Score list create date to')

    @api.multi
    def search_supplier_company_delete(self):
        domain = [('state','!=','done')]
        for wizard in self:
            if datetime.strptime(wizard.date_end,'%Y-%m-%d')-datetime.strptime(
                    wizard.date_begin,'%Y-%m-%d')>timedelta(days=30):
                raise UserError('同时只可以删除一个评分周期内的资料')
            if wizard.plant_id:
                domain+=[('plant_id','=',wizard.plant_id.id)]
            if wizard.supplier_company_id:
                domain+=[('supplier_company_id','=',wizard.supplier_company_id.id)]
            if wizard.date_begin:
                domain+=[('create_date','>=',wizard.date_begin)]
            if wizard.date_end:
                domain+=[('create_date','<=',wizard.date_end)]
            result = self.env['iac.score.list.inherit'].search(domain)
            if not result:
                raise UserError('查无资料')

        action = {
            'domain': [('id', 'in', [x.id for x in result])],
            'name': 'Supplier Company Delete List',
            'type': 'ir.actions.act_window',
            # 'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'iac.score.list.inherit'
        }
        return action
