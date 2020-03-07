# -*- coding: utf-8 -*-

import json
import xlwt
import time, base64
import datetime
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from xlrd import open_workbook
from odoo import models, fields, api, exceptions
import psycopg2
import logging
from dateutil.relativedelta import relativedelta
from StringIO import StringIO
import pdb
import math
import traceback
import utility
from iac_rfq_import import IacRfqImport

_logger = logging.getLogger(__name__)


def is_float_valid(str_val):
    """
    返回2个值
    对出现科学计数法的字符串转换为标准字符串
    1   处理是否成功
    2   转换成的数值
    :param str_val:
    :return:
    """
    try:
        float_val = float(str_val)
        # 获取允许范围之外的小数部分
        input_price = float_val

        # 扩大10 的6次方倍
        try_price = input_price * math.pow(10, 6)

        # 减去整数部分获得小数部分
        digits_part = abs(round(try_price - round(try_price), 2))
        price_unit = 0
        # 如果小数部分大于0.0001 那么表示超过6位，反之小于6位
        if (digits_part > 0.0001):
            # 1000的不满足,尝试10000
            return False, "%f" % (float_val,)
        else:
            return True, "%f" % (float_val,)
    except:
        traceback.print_exc()
        pass
    return False, 0


# Ning add
class IacRfqImportBuyer(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.import.buyer'
    _inherit = 'iac.rfq.import'
    _table = 'iac_rfq_import'
    _order = 'id desc'


# end

class IacRfqImportAs(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.import.as'
    _inherit = 'iac.rfq.import'
    _table = 'iac_rfq_import'
    _order = 'id desc'

    # @api.multi
    # def write(self, vals):
    #     result = super(IacRfqImport, self).write(vals)
    #     return result

    @api.multi
    def save_costup_reason(self):
        """
        校验保存rfq涨价原因
        :return:
        """
        if self.filtered(lambda x: x.state != 'reason'):
            raise UserError(_('State must be reason'))
        for record in self:
            # 调用utility里公用方法校验
            utility.validate_costup_reason(self, record, 'reason')

        return self.env['warning_box'].info(title=u"提示信息", message=u"保存价格不同原因并送MM成功！")

    @api.multi
    def set_to_cancel(self):
        for rfq_line in self:
            if rfq_line.state not in ['as_uploaded', 'reason']:
                continue
            rfq_line.write({"state": "cancel"})

    @api.multi
    def button_search_other_price(self):
        """
        查看此笔RFQ之前上传的所有有效记录
        :return:
        """
        action = self.env.ref("oscg_rfq.action_iac_rfq_import_other_price_form")
        action_window = {
            'name': action.name,
            # 'help': action.help,
            'type': action.type,
            'view_type': "form",
            'view_mode': "form",
            'target': 'current',
            'view_id': self.env.ref('oscg_rfq.view_iac_rfq_import_other_price_form').id,
            'res_id': self.id,
            'res_model': action.res_model,
        }
        return action_window

    @api.one
    def apply_import(self):
        """
        校验当数据是否能够导入到中间表中
        :return:
        """
        if self.valid_from > self.valid_to:
            raise UserError('valid_from can not grater then valid_to,name is: %s' % self.name)

        delta = relativedelta(fields.Date.from_string(self.valid_to), fields.Date.from_string(self.valid_from))
        if delta.years >= 2:
            raise ValidationError(_('Valid to date - Valid from date > 2 years!'))

        # 校验是否有重复数据
        # domain=[('state','in',['draft','sent','replay','wf_fail','wf_unapproved','wf_approved','sap_fail'])]
        domain = [('state', 'in', ['draft', 'sent', 'replay', 'wf_fail', 'wf_approved', 'sap_fail'])]
        domain += [('type', '=', 'rfq')]
        domain += [('vendor_id', '=', self.vendor_id.id)]
        domain += [('part_id', '=', self.part_id.id)]
        rfq_rec = self.env["iac.rfq"].search(domain, order='id desc', limit=1)
        # print self.part_id.part_no,self.vendor_id.vendor_code,rfq_rec.name,rfq_rec.state,rfq_rec.buyer_code.buyer_name
        if rfq_rec.exists():
            # raise UserError('A RFQ  with same vendor and part already exists; name is %s'%rfq_rec.name)
            raise UserError(u'料号%s+厂商%s有一笔流程中的RFQ，号码是%s，状态是%s，请联系采购%s处理，流程结束后或者抽单后再上传新Rfq' % (self.part_id.part_no,
                                                                                              self.vendor_id.vendor_code,
                                                                                              rfq_rec.name,
                                                                                              rfq_rec.state,
                                                                                              rfq_rec.buyer_code.buyer_name))
        # 校验是否存在已经上传的相同料号和厂商
        domain = [('state', 'in', ['as_uploaded', 'reason'])]
        domain += [('vendor_id', '=', self.vendor_id.id)]
        domain += [('part_id', '=', self.part_id.id)]
        domain += [('id', '!=', self.id)]
        last_import_rec = self.env["iac.rfq.import"].search(domain, order='id desc', limit=1)
        if last_import_rec.exists():
            raise UserError('Vendor Code is  (%s),Part No is (%s) upload data has existed' % (
            last_import_rec.vendor_id.vendor_code, last_import_rec.part_id.part_no,))

        # 检厂商状态是否为done
        if self.vendor_id.state != 'done':
            raise UserError(_(
                '厂商 %s的状态不为done无法上传，请联系采购%s处理' % (self.vendor_id.vendor_code, self.part_id.buyer_code_id.buyer_name,)))


class IacRfqImportAsWizardImport(models.TransientModel):
    _name = 'iac.rfq.import.as.wizard'
    _inherit = 'iac.file.import'

    @api.multi
    def action_upload_file(self):
        """
        上传文件按钮入口
        :return:
        """
        # 添加独立的检验，主要就是提前校验Division的有效性
        # print self.file
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        sheet_obj = excel_obj.sheet_by_index(0)
        rows = sheet_obj.nrows
        print rows, sheet_obj.cell(0, 0).value
        plant_list = []
        division_no = []
        division_plant_no = []
        division_plant_cm_no = []
        division_row = []
        division_list = []
        division_plant = []
        division_plant_cm = []

        for i in range(1, rows):

            division = self.env['material.master.asn'].search(['&', ('plant_code', '=', sheet_obj.cell(i, 1).value),
                                                               ('part_no', '=', sheet_obj.cell(i, 3).value)]).division

            if division:
                # 檢查 Division 是否有效
                self._cr.execute(
                    """select  division,* from iac_tmjkburelation where validflag = 'Y' and division = %s """,
                    (division,))
                search_result = self._cr.fetchall()
                print search_result
                if search_result:
                    # 檢查該 Division 與 Plant 是否匹配
                    self._cr.execute(""" select * from iac_bg_division_info where plant = %s and division = %s """,
                                     (sheet_obj.cell(i, 1).value, division))
                    search_plant_division = self._cr.fetchall()
                    if search_plant_division:
                        # 檢查 Plant + Division 是否有設定簽核人員,關卡 = CM
                        self._cr.execute(
                            """ select * from iac_tgroupuserinfo  where plant = %s and divisioncode = %s and levelname = 'CM' """,
                            (sheet_obj.cell(i, 1).value, division))
                        search_cm = self._cr.fetchall()
                        if not search_cm:
                            # 檢查 Plant 下所有 Division 是否有設定簽核人員,關卡 = CM
                            self._cr.execute(
                                """ select * from iac_tgroupuserinfo  where plant = %s and divisionname = 'ALL' and levelname = 'CM' """,
                                (sheet_obj.cell(i, 1).value,))
                            search_cm_all = self._cr.fetchall()
                            if not search_cm_all:
                                division_plant_cm_no.append(int(division))
                                division_plant_cm.append(i + 1)
                                # raise UserError(u'资料第%s行的料號對應的division %s 在webflow中沒有設定簽核關係，請確認料號與division的關係是否正確，如果關係不正確請修改對應關係;如果要新增簽核關係請聯繫8585設定' %(i,division))
                    else:
                        division_plant.append(i + 1)
                        division_plant_no.append(int(division))
                        plant_list.append(str(sheet_obj.cell(i, 1).value))
                        # raise UserError(u'资料第%s行的Division %s 不屬於 plant %s， 請與IT PM確認'%(i,division, sheet_obj.cell(i, 1).value))
                else:
                    division_list.append(i + 1)
                    division_no.append(int(division))
                    # raise UserError(u'资料第%s行的料號對應的Division %s不可用，請修改料號對應的division后重新上傳'%(i,division))
            else:
                division_row.append(i + 1)
        if division_row:
            raise UserError(u'请检查Excel第%s行plant和item_no是否填写正确' % (division_row))
        if division_list:
            raise UserError(u'Excel资料第%s行的料號對應的Division %s不可用，請修改料號對應的division后重新上傳' % (division_list, division_no))
        if division_plant:
            raise UserError(u'Excel资料第%s行的Division %s 不屬於 plant %s，请修改料号对应的division或者通过8585申请设定webflow对应的签核关系' % (
            division_plant, division_plant_no, plant_list))
        if division_plant_cm:
            raise UserError(
                u'Excel资料第%s行的料號對應的division %s 在webflow中沒有設定簽核關係，請確認料號與division的關係是否正確，如果關係不正確請修改對應關係;如果要新增簽核關係請聯繫8585設定' % (
                division_plant_cm, division_plant_cm_no))

        # 检验料号状态是否为01或02
        material_status_id = self.env['material.master'].search([('plant_code', '=', sheet_obj.cell(i, 1).value),
                                                                 ('part_no', '=',
                                                                  sheet_obj.cell(i, 3).value)]).part_status_id
        if material_status_id.part_status in ('04', '10', '12'):
            raise UserError(u'料号 %s 的状态为 %s(%s)，请联系相关人员到PLM系统开单修改料号状态!' % (
                sheet_obj.cell(i, 3).value, material_status_id.part_status,
                material_status_id.description))

        model_name = "iac.rfq.import.as"
        fields = ['id', 'plant_id', 'vendor_id', 'part_code', 'currency_id', 'input_price', 'valid_from', 'valid_to',
                  'price_control', 'note', 'vendor_part_no', 'costup_reason_id']
        process_result, import_result, action_url = super(IacRfqImportAsWizardImport, self).import_file(model_name,
                                                                                                        fields)
        if process_result == False:
            return action_url

        # 导入成功的情况下,转入数据到正式表中
        file_vals = {
            'name': 'import-error-messages',
            'datas_fname': 'import-error-messages.xls',
            'description': 'rfq import error messages',
            'type': 'binary',
            'db_datas': self.file,
        }
        file_rec = self.env['ir.attachment'].create(file_vals)
        import_vals = {
            'state': 'as_uploaded',
            'as_file_id': file_rec.id,
            'new_type': 'as_upload'
        }
        ids = import_result.get('ids')
        # 这里的res_model是由action 的context 传入,代表目标表模型
        import_result = self.env[self.res_model].browse(ids)
        import_result.write(import_vals)

        ex_message_list = []
        for num, rfq_line in enumerate(import_result):
            # 校验source code 是否一致
            # if rfq_line.source_code not in self.env.user.source_code_list:
            #    raise UserError('Part no is (%s),Source Code is (%s) access dined' %(rfq_line.part_id.part_no,rfq_line.part_id.sourcer))
            # 校验厂别是否一致
            if rfq_line.plant_id.id not in self.env.user.plant_id_list:
                raise UserError('Plant Code is (%s) access dined' % (rfq_line.plant_id.plant_code,))
            rfq_line.apply_import()
            update_vals = {
                "import_source": "as_import",
            }
            rfq_line.write(update_vals)

            # 调用公用方法产生新旧rfq对照资料，----->iac.rfq.new.vs.old
            proce_result = utility.create_rfq_new_vs_old(self, rfq_line, 'import_rfq_id', rfq_line.costup_reason_id)
            if proce_result == False and rfq_line.costup_reason_id.id:
                err_msg = 'Plant Code(%s) Vendor Code(%s) Part Code(%s)此笔Info record不存在其他较低单价,请不要填写价格不同原因代码' % \
                          ((rfq_line.plant_id.plant_code, rfq_line.vendor_id.vendor_code, rfq_line.part_id.part_no))
                ex_message_vals = {
                    "message": err_msg,
                    'rows': {
                        "from": num,
                        "to": num,
                    }
                }
                ex_message_list.append(ex_message_vals)
        if len(ex_message_list) > 0:
            self.env.cr.rollback()
            upload_res, act_url = utility.download_error_excel(self, ex_message_list)
            if upload_res == False:
                return act_url
                # raise UserError('请查看跳转链接excel的错误提示')

        return self.env['warning_box'].info(title=u"提示信息", message=u"导入数据操作成功！")

    def validate_parsed_data(self, data, import_fields):
        """
        校验刚刚通过解析的数据,子类可以重写当前函数,实现自定义的解析
        返回值有2个
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        ex_message_list = []
        vendor_part_list = []

        for num, data_line in enumerate(data):
            # 如果有涨价原因，调用方法检验
            if data_line[11]:
                process_msg, process_result = utility.parse_costup_reason_true(self, data_line[11])
                if process_result == False:
                    err_msg = process_msg % (data_line[2], data_line[3])
                    ex_message_vals = {
                        "message": err_msg,
                        'rows': {
                            "from": num,
                            "to": num,
                        }
                    }
                    ex_message_list.append(ex_message_vals)

            if list((data_line[2], data_line[3])) not in vendor_part_list:
                vendor_part_list.append(list((data_line[2], data_line[3])))

            else:
                err_msg = u'表格资料里vendor(%s)part_no(%s)有重复item,请检查' % (data_line[2], data_line[3])
                process_result = False
                ex_message_vals = {
                    "message": err_msg,
                    'rows': {
                        "from": num,
                        "to": num,
                    }
                }
                ex_message_list.append(ex_message_vals)

            field_index = import_fields.index("input_price")
            field_val = data_line[field_index]

            process_result, float_vals = is_float_valid(field_val)
            if process_result == False:
                err_msg = u'小数位数不能超过6位或者非法字符串,小数值位 ( %s )' % (field_val)
                process_result = False
                ex_message_vals = {
                    "message": err_msg,
                    'rows': {
                        "from": num,
                        "to": num,
                    }
                }
                ex_message_list.append(ex_message_vals)

        if len(ex_message_list) > 0:
            return False, ex_message_list
        return True, []

    def validate_imported_data(self, import_result):
        """
        校验刚刚通过导入的的数据,子类可以重写当前函数,实现自定义的校验过程
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        return True, []

    @api.multi
    def action_download_file(self):
        file_dir = self.env["muk_dms.directory"].search([('name', '=', 'file_template')], limit=1, order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template = self.env["muk_dms.file"].search([('filename', '=', 'as_rfq_import.xls')], limit=1,
                                                        order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!' % ("as_rfq_import.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s' % (file_template.id,),
            'target': 'new',
        }
        return action
