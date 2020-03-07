# -*- coding: utf-8 -*-

import json
import xlwt
import time, base64
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
from odoo.tools.safe_eval import safe_eval as eval
import traceback, logging, types, json
import math
import traceback
import utility

# from iac_rfq_cost_up import IacRfqNewVsOld
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


class IacRfqDownloadWizard(models.TransientModel):
    """mm下载rfq,选择查询条件进行下载：
    """
    _name = 'iac.rfq.download.wizard'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    division_id = fields.Many2one('division.code', string='Division Info')
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")

    @api.multi
    def action_confirm(self):
        """
        MM下载自己归属的rfq,这些rfq是AS先前上传的
        :return:
        """

        rfq_import = self.env["iac.rfq.import.mm"].search([('state', '=', 'as_uploaded')])
        rfq_line_id_list = []
        for rfq_line in rfq_import:
            # 判断是否要导出数据
            if rfq_line.buyer_code.id in self.env.user.buyer_id_list:
                rfq_line_id_list.append(rfq_line.id)
        header_field_list = []
        header_field_list = ['as_upload_id', 'plant_id', 'vendor_id', 'part_code', 'currency_id', 'input_price',
                             'valid_from', 'valid_to', 'price_control', 'note', 'vendor_part_no', 'lt', 'moq', 'mpq',
                             'cw', 'rw', 'tax']

        output = StringIO()
        wb2 = xlwt.Workbook()
        sheet1 = wb2.add_sheet('sheet1', cell_overwrite_ok=True)
        # 写excel文件的表头
        for i in xrange(len(header_field_list)):
            sheet1.write(0, i, header_field_list[i])
        # sheet1.write(0,sheet.ncols,'message')
        # write messages
        r = 1
        # lt	moq	mpq	cw	rw	tax

        blank_filed_list = ['lt', 'moq', 'mpq', 'rw', 'cw', 'tax']
        for rfq_line in self.env["iac.rfq.import.mm"].browse(rfq_line_id_list):
            domain = [('part_id', '=', rfq_line.part_id.id), ('vendor_id', '=', rfq_line.vendor_id.id),
                      ('state', '=', 'sap_ok')]
            domain += [('currency_id', '=', rfq_line.currency_id.id)]
            last_rfq_line = self.env["iac.rfq"].search(domain, limit=1, order='create_date desc')
            for i in xrange(len(rfq_line.ids)):
                for j in xrange(len(header_field_list)):
                    # if header_field_list[j]in blank_filed_list:
                    #    continue
                    # 值为空的字段不写入数据
                    if getattr(rfq_line, header_field_list[j]) == False and (
                            header_field_list[j] == 'note' or header_field_list[j] == 'vendor_part_no'):
                        continue
                    if header_field_list[j] == 'currency_id':
                        sheet1.write(r, j, rfq_line.currency_id.name)
                    elif header_field_list[j] == 'plant_id':
                        sheet1.write(r, j, rfq_line.plant_id.plant_code)
                    elif header_field_list[j] == 'vendor_id':
                        sheet1.write(r, j, rfq_line.vendor_id.vendor_code)
                    elif header_field_list[j] == 'as_upload_id':
                        sheet1.write(r, j, rfq_line.id)
                    elif header_field_list[j] == 'lt':
                        if rfq_line.lt != False:
                            sheet1.write(r, j, rfq_line.lt)
                        elif rfq_line.lt == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.lt)
                    elif header_field_list[j] == 'moq':
                        if rfq_line.moq != False:
                            sheet1.write(r, j, rfq_line.moq)
                        elif rfq_line.moq == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.moq)
                    elif header_field_list[j] == 'mpq':
                        if rfq_line.mpq != False:
                            sheet1.write(r, j, rfq_line.mpq)
                        elif rfq_line.mpq == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.mpq)
                    elif header_field_list[j] == 'rw':
                        if rfq_line.rw != False:
                            sheet1.write(r, j, rfq_line.rw)
                        elif rfq_line.rw == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.rw)
                    elif header_field_list[j] == 'cw':
                        if rfq_line.cw != False:
                            sheet1.write(r, j, rfq_line.cw)
                        elif rfq_line.cw == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.cw)
                    elif header_field_list[j] == 'tax':
                        if rfq_line.tax != False:
                            sheet1.write(r, j, rfq_line.tax)
                        elif rfq_line.tax == False and last_rfq_line.exists():
                            sheet1.write(r, j, last_rfq_line.tax)
                    else:
                        sheet1.write(r, j, getattr(rfq_line, header_field_list[j]))
                    # sheet1.write(r,j, sheet.cell(i+1,j).value)
                r += 1
        wb2.save(output)

        # 文件输出成功之后,跳转链接，浏览器下载文件
        vals = {
            'name': 'rfq_line_mm_downloads',
            'datas_fname': 'rfq_line_mm_downloads.xls',
            'description': 'MM Download As Upload Rfq',
            'type': 'binary',
            'db_datas': base64.encodestring(output.getvalue()),
        }
        file = self.env['ir.attachment'].create(vals)
        action = {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s.xls' % (file.id, file.id,),
            'target': 'new',
        }

        return action


class IacRfqImportMM(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.import.mm'
    _inherit = 'iac.rfq.import'
    _table = 'iac_rfq_import'
    _order = 'as_file_id desc,id asc'

    @api.one
    def related_newvsold_rfq(self):
        """
        更新iac_rfq_new_vs_old的current_rfq_id
        :return:
        """
        # 查询到此笔rfq之前as上传的时候iac_rfq_inport与老rfq绑定的记录
        related_new_olds = self.env['iac.rfq.new.vs.old'].search([('import_rfq_id', '=', self.as_upload_id.id),
                                                                  ('current_rfq_id', '=', False)])
        for new_vs_old in related_new_olds:
            new_vs_old.write({'current_rfq_id': self.rfq_id.id})

    @api.one
    def apply_mm_update(self):
        """
        导入当前记录的数据到iac_rfq正式表中
        :return:
        """

        # 校验是否有重复数据
        # domain=[('state','in',['draft','sent','replay','wf_fail','wf_unapproved','wf_approved','sap_fail'])]
        domain = [('state', 'in', ['draft', 'sent', 'replay', 'wf_fail', 'wf_approved', 'sap_fail'])]
        domain += [('type', '=', 'rfq')]
        domain += [('vendor_id', '=', self.vendor_id.id)]
        domain += [('part_id', '=', self.part_id.id)]
        rfq_rec = self.env["iac.rfq"].search(domain, order='id desc', limit=1)
        if rfq_rec.exists():
            raise UserError('A RFQ  with same vendor and part already exists; name is %s' % rfq_rec.name)

        fields = ['part_code', 'input_price', 'valid_from', 'valid_to', 'price_control', 'note', 'vendor_part_no']
        fields = fields + ['moq', 'mpq', 'lt', 'cw', 'rw', 'tax']
        vals_list = self.read(fields)
        for vals in vals_list:
            vals["plant_id"] = self.plant_id.id
            vals["part_id"] = self.part_id.id
            vals["vendor_id"] = self.vendor_id.id
            vals["currency_id"] = self.currency_id.id
            vals["buyer_code"] = self.part_id.buyer_code_id.id
            vals["new_type"] = "buyer_create"
            vals["type"] = "rfq"
            vals["state"] = "rfq"
            # 涨价原因_by_jiangjun
            vals['cost_up_reason_id'] = self.costup_reason_id.id
            new_rfq_rec = self.env["iac.rfq"].create(vals)
            self.write({"rfq_id": new_rfq_rec.id})

        # 调用utility里公用方法产生对照资料
        utility.create_rfq_new_vs_old(self, self, 'import_rfq_id', self.costup_reason_id)
        # 调用方法更新iac.rfq.new.vs.old的current_rfq_id
        # 使对iac.rfq.new.vs.old的资料和iac_rfq的资料产生关联_by_jiangjun
        self.related_newvsold_rfq()

    @api.multi
    def button_to_download(self):
        """
        MM下载自己归属的rfq,这些rfq是AS先前上传的
        :return:
        """

        # 获取buyer_code
        # buyer_code_list=[]
        # for buyer_id in self.env.user.partner_id.buyer_code:
        #    buyer_code_list.append(buyer_id.buyer_erp_id)
        rfq_import = self.search([('state', '=', 'as_uploaded')])
        rfq_line_id_list = []
        for rfq_line in rfq_import:
            # 判断是否要导出数据
            if rfq_line.part_id.buyer_code_id in self.env.user.buyer_id_list:
                rfq_line_id_list.append(rfq_line.id)
        header_field_list = []
        header_field_list = ['id', 'plant_id', 'vendor_id', 'part_code', 'currency_id', 'input_price', 'valid_from',
                             'valid_to', 'price_control', 'note', 'vendor_part_no', 'lt', 'moq', 'mpq', 'cw', 'rw',
                             'tax']

        output = StringIO()
        wb2 = xlwt.Workbook()
        sheet1 = wb2.add_sheet('sheet1', cell_overwrite_ok=True)
        # 写excel文件的表头
        for i in xrange(len(header_field_list)):
            sheet1.write(0, i, header_field_list[i])
        # sheet1.write(0,sheet.ncols,'message')
        # write messages
        r = 1
        for rfq_line in self.browse(rfq_line_id_list):
            for i in xrange(len(rfq_line.ids)):
                for j in xrange(len(header_field_list)):
                    if header_field_list[j] == 'currency_id':
                        sheet1.write(r, j, rfq_line.currency_id.name)
                    elif header_field_list[j] == 'plant_id':
                        sheet1.write(r, j, rfq_line.plant_id.plant_code)
                    elif header_field_list[j] == 'vendor_id':
                        sheet1.write(r, j, rfq_line.vendor_id.vendor_code)
                    else:
                        sheet1.write(r, j, getattr(rfq_line, header_field_list[j]))
                    # sheet1.write(r,j, sheet.cell(i+1,j).value)
                r += 1
        wb2.save(output)

        # 文件输出成功之后,跳转链接，浏览器下载文件
        vals = {
            'name': 'rfq_line_mm_downloads',
            'datas_fname': 'rfq_line_mm_downloads.xls',
            'description': 'MM Download As Upload Rfq',
            'type': 'binary',
            'db_datas': base64.encodestring(output.getvalue()),
        }
        file = self.env['ir.attachment'].create(vals)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s.xls' % (file.id, file.id,),
            'target': 'new',
        }


class IacRfqMMRelease(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.mm.release'
    _inherit = 'iac.rfq'
    _table = 'iac_rfq'
    _order = 'id desc'

    approve_role_list = fields.Char(string="Approve Role List")

    @api.multi
    def button_to_get_approve_list(self):
        """计算当前RFQ的签核角色信息列表"""

        expressions = self.env['iac.rfq.qh'].search([])

        # 遍历选中的RFQ计算规则
        for rfq_line in self:
            role_list = []
            proc_ex_list = []
            rule_name_list = []
            for exp in expressions:
                eval_context = {
                    "r": rfq_line
                }
                # 判断规则是否判断通过
                try:
                    if eval(exp.key, eval_context):
                        role_list += eval(exp.value)
                        rule_name_list.append(exp.name)
                except:
                    traceback.print_exc()
                    err_msg = "rule eval error,name is (%s);\n error info is %s" % (exp.name, traceback.format_exc())
                    proc_ex_list.append(err_msg)
            # 写入获取角色列表信息
            approve_role_list = {
                "role_list": sorted(list(set(role_list))),
                "rule_name_list": rule_name_list
            }
            vals = {
                "approve_role_list": approve_role_list,
                "webflow_result": proc_ex_list,
            }
            rfq_line.write(vals)

    @api.multi
    def action_cancel(self):
        if self.filtered(lambda x: x.state not in ['draft', 'replay', 'rfq', 'wf_unapproved']):
            raise UserError(_('State must be draft or replay or rfq or wf_unapproved !'))
        for item in self:
            val = {}
            # print rfq_line.id
            val['rfq_id'] = item.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'MM no action required'
            self.env['iac.rfq.quote.history'].create(val)
        self.write({'state': 'cancel', 'active': False})

    @api.multi
    def action_restate_rfq(self):
        self.filtered(lambda x: x.state in ['wf_fail', 'sap_fail', 'wf_unapproved']).write({'state': 'rfq'})

    @api.multi
    def action_send_to_sap(self):
        """
        可以选择多条记录送SAP系统,只能对sap_fail状态的rfq使用
        :return:
        """
        for rfq_rec in self:
            if rfq_rec.state not in ['sap_fail', 'wf_approved']:
                raise UserError(
                    "RFQ NO is %s is not in state 'sap_fail,wf_approved' ,Can not send to sap" % (rfq_rec.name,))
            val = {}
            # print rfq_line.id
            val['rfq_id'] = rfq_rec.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'MM send to SAP'
            self.env['iac.rfq.quote.history'].create(val)

            rpc_result, rpc_json_data, log_line_id, exception_log = rfq_rec.sap_odoo_rfq_001()


class IacRfqImportMMWizard(models.TransientModel):
    _name = 'iac.rfq.import.mm.wizard'
    _inherit = 'iac.file.import'

    @api.multi
    def action_upload_file(self):
        """
        上传文件按钮入口
        :return:
        """

        # user上传前判断税率 190430 ning add begin
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        sheet_obj = excel_obj.sheet_by_index(0)
        error_str = ''
        for rx in range(sheet_obj.nrows):
            if rx >= 1:
                if sheet_obj.cell(rx, 1).value == 'TP02' and sheet_obj.cell(rx, 4).value != 'TWD' and sheet_obj.cell(rx,
                                                                                                                     16).value != 'V0':
                    error_str = error_str + str(rx + 1) + ','
        if error_str:
            raise UserError('第' + error_str + '行资料错误,厂区为TP02的并且币种不是台币的情况下,tax 必须为 V0')
        # end
        # 检验料号状态是否为01或02
        rows = sheet_obj.nrows
        print rows, sheet_obj.cell(0, 0).value
        for i in range(1, rows):
            material_status_id = self.env['material.master'].search([('plant_code', '=', sheet_obj.cell(i, 1).value),
                                                                     ('part_no', '=',
                                                                      sheet_obj.cell(i, 3).value)]).part_status_id
            if material_status_id.part_status in ('04', '10', '12'):
                raise UserError(u'料号 %s 的状态为 %s(%s)，请联系相关人员到PLM系统开单修改料号状态!' % (
                    sheet_obj.cell(i, 3).value, material_status_id.part_status,
                    material_status_id.description))

        model_name = "iac.rfq.import.as"

        fields = ['as_upload_id_value', 'plant_id', 'vendor_id', 'part_code', 'currency_id', 'input_price',
                  'valid_from', 'valid_to', 'price_control', 'note', 'vendor_part_no', 'lt', 'moq', 'mpq', 'cw', 'rw',
                  'tax']
        process_result, import_result, action_url = super(IacRfqImportMMWizard, self).import_file(model_name, fields)

        if process_result == False:
            # 当mm上传的数据存在问题的时候自动修改状态为cancel
            import_rfq_lines = self.env["iac.rfq.import.as"].sudo().browse(import_result.get("ids"))
            for rfq_line in import_rfq_lines:
                update_vals = {
                    "import_source": "mm_import",
                    "state": "mm_update_fail"
                }
                rfq_line.write(update_vals)
                # rfq_line.write({"state":"cancel"})
            return action_url

        # mm上传记录并不在原有记录上面修改，而是新建记录，所以需要将先前as上传的记录状态设置为删除
        import_rfq_lines = self.env["iac.rfq.import.as"].sudo().browse(import_result.get("ids"))
        for rfq_line in import_rfq_lines:
            update_vals = {
                "import_source": "mm_import",
                "state": "mm_updated",
                'costup_reason_id': rfq_line.as_upload_id.costup_reason_id.id
            }
            rfq_line.write(update_vals)

            # rfq_line.write({"state":"mm_updated"})
            # rfq_line.as_upload_id.write({"state":"cancel"})
            rfq_line.as_upload_id.write({"state": "done"})

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
            'state': 'mm_updated',
            'mm_file_id': file_rec.id,
        }
        ids = import_result["ids"]
        # 这里的res_model是由action 的context 传入,代表目标表模型
        self.env[self.res_model].browse(ids).write(import_vals)
        for rfq_line in self.env[self.res_model].browse(ids):
            rfq_line.apply_mm_update()

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
        for num, data_line in enumerate(data):
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
        {
         "message"::"错误信息",
         "rows":{
             "from":1,
             "to":1
         }
        }
        :return:
        """
        process_result = True
        ex_list = []
        import_rfq_lines = self.env["iac.rfq.import.as"].browse(import_result.get("ids"))

        for rfq_line in import_rfq_lines:
            # 验证as_upload_id_value 确保正确
            as_upload_rfq_line = self.env["iac.rfq.import"].browse(rfq_line.as_upload_id_value)
            if not as_upload_rfq_line.exists():
                process_result = False
                ex_vals = {
                    "message": "AS Upload Info Does not exists,ref id is not valid",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)
                continue
            else:
                rfq_line.write({"as_upload_id": rfq_line.as_upload_id_value})

            if not rfq_line.as_upload_id.exists():
                process_result = False
                ex_vals = {
                    "message": "AS Upload Info Does not exists",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)
                continue
            if rfq_line.as_upload_id.state != "as_uploaded":
                process_result = False
                ex_vals = {
                    "message": "AS upload data state is not valid",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.plant_id.id != rfq_line.as_upload_id.plant_id.id:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify plant info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)
            if rfq_line.vendor_id.id != rfq_line.as_upload_id.vendor_id.id:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify vendor info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.part_id.id != rfq_line.as_upload_id.part_id.id:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify part info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.currency_id.id != rfq_line.as_upload_id.currency_id.id:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify Currency info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)
            if rfq_line.input_price != rfq_line.as_upload_id.input_price:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify Price info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.valid_from != rfq_line.as_upload_id.valid_from:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify Valid From info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.valid_to != rfq_line.as_upload_id.valid_to:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify Valid From info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.price_control != rfq_line.as_upload_id.price_control:
                process_result = False
                ex_vals = {
                    "message": "MM can not modify price control info",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.cw == False:
                process_result = False
                ex_vals = {
                    "message": "cw can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)
            if rfq_line.rw == False:
                process_result = False
                ex_vals = {
                    "message": "rw can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.tax == False:
                process_result = False
                ex_vals = {
                    "message": "tax can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.lt == False:
                process_result = False
                ex_vals = {
                    "message": "lt can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.moq == False:
                process_result = False
                ex_vals = {
                    "message": "moq can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

            if rfq_line.mpq == False:
                process_result = False
                ex_vals = {
                    "message": "mpq can not be null",
                    "rows": {
                        "from": rfq_line.file_line_no - 1,
                        "to": rfq_line.file_line_no - 1,
                    }
                }
                ex_list.append(ex_vals)

        return process_result, ex_list
