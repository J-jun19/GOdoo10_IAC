# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
from xlrd import open_workbook
from odoo import exceptions
# from datetime import datetime
import traceback
from odoo.odoo_env import odoo_env
import datetime


class IacCustomsSasHeader(models.Model):
    """ 出入库单header """
    _name = "iac.customs.sas.header"
    _table = "iac_customs_sas_header"
    _order = 'id desc'

    sas_stock_no = fields.Char(string=u'出入库单编号')
    dcl_type_cd = fields.Selection([("1",u"备案"),("2",u"变更"),("3",u"作废")],string=u"申报类型",default="1")
    sas_dcl_no = fields.Char(string=u'申报表编号')
    sas_stock_preent_no = fields.Char(string=u'预录入编号')
    master_cuscd = fields.Char(string=u'关区')
    stock_typecd = fields.Selection([("I",u"进区"),("E",u"出区")],string=u"出入库单类型",default="I")
    business_typecd = fields.Char(string=u'业务类型')
    centralized_dcl_typecd = fields.Selection([("1",u"未集报"),("2",u"已集报")],string=u"海关集报标志",default="1")
    dcl_er = fields.Char(string=u'申请人')
    package_qty = fields.Float(string=u'件数',digits=(19,5))
    gross_wt = fields.Float(string=u'毛重',digits=(19,5))
    net_wt = fields.Float(string=u'净重',digits=(19,5))
    pack_type = fields.Char(string=u'包装种类')
    pass_typecd = fields.Char(string=u"海关过卡标志")
    passport_used_typecd = fields.Char(string=u"海关核放单生成标志")
    stucd = fields.Char(string=u"海关状态")
    emapv_markcd = fields.Char(string=u"海关审批标志")
    usetocod = fields.Char(string=u'备注')
    owner_system = fields.Selection([("1",u"特殊区域"),("2",u"保税物流")],string=u"所属系统",default="1")
    rtl_typecd = fields.Char(string=u'类型')
    precentralized_dcl_typecd = fields.Char(string=u'集报标志')
    prepass_typecd = fields.Char(string=u'过卡标志')
    prepassport_used_typecd = fields.Char(string=u'核放单生成标志')
    prestucd = fields.Char(string=u'状态')
    state = fields.Selection([("wait_mm_approve",u"待采购确认"),
                              ("wait_lg_approve",u"待关务确认"),
                              ("mm_reject",u"采购拒绝"),
                              ('lg_approved',u'关务核准'),
                              ("lg_reject",u"关务拒绝"),
                              ("interface_submit_success", u"推送海关系统成功"),
                              ("interface_submit_fail", u"推送海关系统失败"),
                              ('cancel', u'厂商取消'),
                              ("to_cancel", u"作废中"),
                              ("done", "done")],string=u"状态")
    has_open_asn = fields.Boolean(string=u'是否有足够的Open ASN')
    vendor_id = fields.Many2one('iac.vendor',string=u'供应商ID',index=True)
    # vendor_name = fields.Many2one('iac.vendor',string=u'Vendor Name')
    plant_id = fields.Many2one('pur.org.data',string=u'工厂ID',index=True)
    lg_approver_id = fields.Many2one('res.users',string=u'关务审核人员ID',index=True)
    lg_approve_time = fields.Datetime(string=u'关务审核时间')
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    orig_sas_id = fields.Integer(string=u'原始出入库单编号ID')
    orig_sas_no = fields.Char(string=u'原始出入库单编号')
    sas_dcl_id = fields.Many2one('iac.customs.sas.declare', string=u'业务申报表id', index=True)
    customs_id = fields.Char(string=u'海关返回ID')
    customs_back_id = fields.Char(string=u'海关返回ID备份')
    org_code = fields.Char(string=u'组织编号')
    sas_stock_line_ids = fields.One2many('iac.customs.sas.line', 'sas_stock_id', string=u'出入库单line ID', index=True)
    pass_port_id = fields.Many2one('iac.customs.pass.port.header',string=u'核放单Header ID',index=True)
    pass_port_no = fields.Char(string=u'核放单编号')
    export_flag = fields.Integer(string=u'已开出库单标志')
    opt_status = fields.Selection([("1",u"暂存"),
                                   ("3",u"海关入库"),
                                   ("4",u"海关入库失败"),
                                   ('5',u'审核通过'),
                                   ("6",u"审核拒绝"),
                                   ("16", u"正在申报"),
                                   ("17", u"转人工"),
                                   ("18", u"已申报"),
                                   ("19", u"申报失败"),
                                   ('95', u'作废申报'),
                                   ("96", u"已作废"),
                                   ("99", u"删除")],string=u"海关审批状态")
    opt_remark = fields.Char(string=u'海关返回信息')
    opt_time = fields.Datetime(string=u'海关审批时间')
    state_back = fields.Char(string=u'备份状态')
    pass_cancel_id = fields.Many2one('iac.customs.pass.port.cancel', string=u'对应的出入库单 ID', index=True)
    buyer_code_ids = fields.One2many('iac.customs.sas.header.vs.buyer.code', 'header_id', string='Buyer code')
    storage_location_id = fields.Many2one('iac.storage.location.address', string='Storage Location', index=True)

    # @api.multi
    # def button_to_approve(self):
    #     for item in self.env.user.groups_id:
    #         if item.name == 'Buyer':
    #             for record in self:
    #                 if record.stock_typecd == 'I':
    #                     self.buyer_to_approve()
    #                 else:
    #                     self.

    @api.multi
    def button_to_approve(self):
        """
        buyer，lg审核出入库单，送签到关务,海关
        :return:
        """
        bol_list = []
        for item in self.env.user.groups_id:
            print item.name
            if item.name == 'Buyer':
                for record in self:
                    # header_id = record.id
                    # 更新本张入库单表体属于当前buyer资料的状态为待关务签核
                    buyer_approve_objs = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',record.id),('state','=','wait_mm_approve')])
                    # obj_lens =len(buyer_approve_objs)
                    # print obj_lens,type(obj_lens)
                    # i = 1
                    try:
                        for approve_obj in buyer_approve_objs:
                            # if approve_obj.part_id.buyer_code_id.id in self.env.user.buyer_id_list:
                            print approve_obj.part_id
                            approve_obj.write({'state': 'wait_lg_approve',
                                               'mm_approver_id': self._uid,
                                               'mm_approve_time': datetime.datetime.now(),
                                               'iac_write_uid': self._uid,
                                               'iac_write_date': datetime.datetime.now()})
                            # approve_obj.env.cr.commit()
                            action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                            'customs_direction': record.stock_typecd,
                                                                                            'sas_stock_id': record.id,
                                                                                            'sas_stock_line_id': approve_obj.id,
                                                                                            'action': 'MM approve create SAS stock',
                                                                                            'iac_write_uid': self._uid,
                                                                                            'iac_write_date': datetime.datetime.now()})

                            # unlink_obj = self.env['buyer.code.iac.customs.sas.header.rel'].sudo().search([('iac_customs_sas_header_id', '=', record.id),
                            #                                                           ('buyer_code_id','=',approve_obj.part_id.buyer_code_id.id)])

                            # unlink_obj = self.env['iac.customs.sas.header.vs.buyer.code'].search([('header_id', '=', record.id),
                            #                                                                       ('buyer_code_id', '=', approve_obj.part_id.buyer_code_id.id)])
                            # # self._cr.execute(""" SELECT * from buyer_code_iac_customs_sas_header_rel where iac_customs_sas_header_id=%s and buyer_code_id=%s """,
                            # #                  (record.id,approve_obj.part_id.buyer_code_id.id))
                            # # unlink_obj = self._cr.fetchall()
                            # if unlink_obj:
                            #     unlink_obj.unlink()

                            # 当某个采购送签完之后就删掉header_id和buyer_code_id对照表的资料，让这个采购看不到这个出入库单的header
                            # sas_buyer_code_id = approve_obj.part_id.buyer_code_id.id
                            # if i == obj_lens:
                            #     unlink_obj = self.env['iac.customs.sas.header.vs.buyer.code'].search([('buyer_code_id','=',sas_buyer_code_id),('header_id','=',record.id)])
                            #     unlink_obj.write({'dele_flag':'1'})
                            # i += 1

                        # 判断整张入库单表体的状态是否都是待关务签核，即是否是最后一个采购签核，如果是就更新表头的状态为待关务签核
                        all_approve_lines = self.env['iac.customs.sas.line'].sudo().search([('sas_stock_id', '=', record.id)])
                        approve_line_qty = 0
                        for approve_line in all_approve_lines:
                            if approve_line.state == 'wait_lg_approve':
                                approve_line_qty += 1
                                continue
                            else:
                                # approve_line_qty += 1
                                break
                        if approve_line_qty == len(all_approve_lines):
                            record.write({'state': 'wait_lg_approve',
                                          'iac_write_uid': self._uid,
                                          'iac_write_date': datetime.datetime.now()})

                    except:
                        self.env.cr.rollback()
                        raise exceptions.ValidationError(u'送签失败！')
            elif item.name == 'LG users':
                bol = self.button_to_customs()
                if bol == False:
                    bol_list.append(bol)
            else:
                continue
        if len(bol_list) > 0:
            message = u'送签失败'
        else:
            message = u'送签成功！'
        return self.env['warning_box'].info(title="Message", message=message)


    @api.multi
    def button_to_reject(self):
        """
        buyer,lg审核出入库单，退件回vendor
        :return:
        """
        for item in self.env.user.groups_id:
            print item.name
            if item.name == 'Buyer':
                for record in self:
                    buyer_approve_objs = self.env['iac.customs.sas.line'].search([('sas_stock_id', '=', record.id), ('state', '=', 'wait_mm_approve')])
                    try:
                        for approve_obj in buyer_approve_objs:
                            if approve_obj.part_id.buyer_code_id.id in self.env.user.buyer_id_list:
                                if record.stock_typecd == 'I':
                                    approve_obj.write({'state': 'mm_reject',
                                                   'valid_export_qty':0,
                                                   'mm_approver_id': self._uid,
                                                   'mm_approve_time': datetime.datetime.now(),
                                                   'iac_write_uid': self._uid,
                                                   'iac_write_date': datetime.datetime.now()})
                                else:
                                    approve_obj.write({'state': 'mm_reject',
                                                       # 'valid_export_qty': 0,
                                                       'mm_approver_id': self._uid,
                                                       'mm_approve_time': datetime.datetime.now(),
                                                       'iac_write_uid': self._uid,
                                                       'iac_write_date': datetime.datetime.now()})
                                    cancel_object = self.env['iac.customs.sas.line.inherit'].browse(approve_obj.orig_sas_line_id.id)
                                    cancel_object.write({
                                        'valid_export_qty': cancel_object.valid_export_qty+approve_obj.dcl_qty
                                    })
                                # approve_obj.env.cr.commit()
                                action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                                    'customs_direction': record.stock_typecd,
                                                                                                    'sas_stock_id': record.id,
                                                                                                    'sas_stock_line_id': approve_obj.id,
                                                                                                    'action': 'MM reject create SAS stock',
                                                                                                    'iac_write_uid': self._uid,
                                                                                                    'iac_write_date': datetime.datetime.now()})
                        # 判断整张入库单表体的状态,如果有一个采购退件，就更新表头的状态为采购退件
                        all_approve_lines = self.env['iac.customs.sas.line'].sudo().search([('sas_stock_id', '=', record.id)])
                        for approve_line in all_approve_lines:
                            # print approve_line.state
                            if approve_line.state == 'mm_reject':
                                record.write({'state': 'mm_reject',
                                              'iac_write_uid': self._uid,
                                              'iac_write_date': datetime.datetime.now()})
                                break
                            # else:
                            #     approve_line_qty += 1
                            #     break
                        # if approve_line_qty == len(all_approve_lines):
                    except:
                        self.env.cr.rollback()
                        # raise exceptions.ValidationError(u'退件失败，请重新操作！')
                        raise exceptions.ValidationError(traceback.format_exc())

            elif item.name == 'LG users':
                self.button_reject_sas()
            else:
                continue
        message = u'退件成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_to_customs(self):
        """
        关务审核出入库单，call海关系统
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'送件功能只允许推送状态为“待关务确认”的资料，请检查！')
            try:
                record.write({'state': 'lg_approved',
                              'lg_approver_id': self._uid,
                              'lg_approve_time': datetime.datetime.now(),
                              'iac_write_uid': self._uid,
                              'iac_write_date': datetime.datetime.now()})
                action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                    'customs_direction': record.stock_typecd,
                                                                                    'sas_stock_id': record.id,
                                                                                    'action': 'LG approve create SAS stock',
                                                                                    'iac_write_uid': self._uid,
                                                                                    'iac_write_date': datetime.datetime.now()})
                # 调用海关出入库单接口 ODOO_CUSTOMS_001
                flag = self.sas_send_to_customs_save(record)
                print flag
                if flag == False:
                    flag_list.append(flag)

            except:
                flag_list.append('1')
                self.env.cr.rollback()
                record.write({'state': 'interface_submit_fail',
                              'lg_approver_id': self._uid,
                              'lg_approve_time': datetime.datetime.now(),
                              'iac_write_uid': self._uid,
                              'iac_write_date': datetime.datetime.now(),
                              'opt_remark': str(traceback.format_exc())})
                record.env.cr.commit()
                # 写log
                for sas_stock_line in record.sas_stock_line_ids:
                    # print sas_stock_line.id
                    vals = {
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.id,
                        'sas_stock_line_id': sas_stock_line.id,
                        'action': 'Call customs interface create SAS stock failed'
                    }
                    hry_obj = self.env['iac.customs.action.history'].create(vals)
                    hry_obj.env.cr.commit()
            # 同时更新对应的line资料的state
            # record_lines = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',record.id)])
            # for record_line in record_lines:
            #     record_line.write({'state'})
        if len(flag_list) > 0:
            return False
        # else:
        #     message = u'推送海关系统成功！'
        # return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_to_customs_again(self):
        """
        关务重送出入库单对于推送海关失败的资料
        :return:
        """
        flag = 0
        for item in self.env.user.groups_id:
            if item.name == 'LG users':
                flag = 1
                break
            else:
                continue
        if flag == 0:
            raise exceptions.ValidationError(u'当前按钮只有关务人员有权限！')
        flag_list = []
        for record in self:
            if record.state != 'interface_submit_fail':
                raise exceptions.ValidationError(u'此按钮只允许推送状态为“推送海关系统失败”的资料，请检查！')
            try:
                record.write({
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now()})

                # 调用海关出入库单接口 ODOO_CUSTOMS_001
                flag = self.sas_send_to_customs_save(record)
                if flag==False:
                    flag_list.append(flag)
                action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                'customs_direction': record.stock_typecd,
                                                                                'sas_stock_id': record.id,
                                                                                'action': 'LG approve fail SAS stock again',
                                                                                'iac_write_uid': self._uid,
                                                                                'iac_write_date': datetime.datetime.now()})
            except:
                self.env.cr.rollback()
                record.write({'state': 'interface_submit_fail',
                              'lg_approver_id': self._uid,
                              'lg_approve_time': datetime.datetime.now(),
                              'iac_write_uid': self._uid,
                              'iac_write_date': datetime.datetime.now(),
                              'opt_remark': str(traceback.format_exc())})
                record.env.cr.commit()
                raise exceptions.ValidationError(u'推送海关系统失败，请重试！')
        if len(flag_list)>0:
            message = u'重送海关系统失败！'
        else:
            message = u'重送海关系统成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_reject_sas(self):
        """
        关务退件出入库单
        :return:
        """
        for record in self:
            if record.state != 'wait_lg_approve' and record.stock_typecd == 'I':
                raise exceptions.ValidationError(u'入库单退件只允许推送状态为“待关务签核”的资料，请检查！')
            try:
                if record.stock_typecd == 'I':
                    record.write({'state': 'lg_reject',
                                  'valid_export_qty': 0,
                                  'lg_approver_id': self._uid,
                                  'lg_approve_time': datetime.datetime.now(),
                                  'iac_write_uid': self._uid,
                                  'iac_write_date': datetime.datetime.now()})
                else:
                    record.write({'state': 'lg_reject',
                                  # 'valid_export_qty': 0,
                                  'lg_approver_id': self._uid,
                                  'lg_approve_time': datetime.datetime.now(),
                                  'iac_write_uid': self._uid,
                                  'iac_write_date': datetime.datetime.now()})
                    godown_line_objects = self.env['iac.customs.sas.line'].search([('sas_stock_id', '=', record.id)])
                    for godown_line_object in godown_line_objects:
                        # entry_object = self.env['iac.customs.sas.header'].browse(record.orig_sas_id)
                        entry_line_object = self.env['iac.customs.sas.line.inherit'].search([('id','=',godown_line_object.orig_sas_line_id.id)])
                        entry_line_object.write({
                        'valid_export_qty': entry_line_object.valid_export_qty + godown_line_object.dcl_qty
                    })
                    # cancel_object = self.env['iac.customs.sas.line'].browse(record.orig_sas_line_id.id)
                    # cancel_object.write({
                    #     'valid_export_qty': cancel_object.valid_export_qty + record.dcl_qty
                    # })
                action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                    'customs_direction': record.stock_typecd,
                                                                                    'sas_stock_id': record.id,
                                                                                    'action': 'LG reject create SAS stock',
                                                                                    'iac_write_uid': self._uid,
                                                                                    'iac_write_date': datetime.datetime.now()})
            except:
                self.env.cr.rollback()
                raise exceptions.ValidationError(u'退件失败，请重试！')

        # message = u'退件成功！'
        # return self.env['warning_box'].info(title="Message", message=message)

    # 从出入库单header表抓取done状态的资料
    @api.multi
    def get_sas_header_data_done(self):
        customs_id_list = []
        self._cr.execute("select * from iac_customs_sas_header where state=%s "
                         "and create_date>=%s and (stucd=%s or (stucd=%s and emapv_markcd=%s and pass_typecd=%s) or stucd is null)",
                         ('done', (datetime.datetime.now() - datetime.timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),'0', '1', '1', '1'))
        for item in self.env.cr.dictfetchall():
            customs_id_list.append(item['customs_id'])
        return customs_id_list

    # 从出入库单header表抓取暂存成功状态的资料
    @api.multi
    def get_sas_header_data_submit(self):
        customs_id_list2 = []
        sas = self.env["iac.customs.sas.header"].search([('state', '=', 'interface_submit_success'),
                                                         ('lg_approve_time','<',(datetime.datetime.now()-datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"))])
        for item2 in sas:
            customs_id_list2.append(item2.customs_id)
        return customs_id_list2

    # 从出入库单cancel表抓取暂存成功状态的资料
    @api.multi
    def get_sas_cancel_data_submit(self):
        customs_id_list3 = []
        sas = self.env["iac.customs.sas.cancel"].search([('state', '=', 'interface_submit_success'),
                                                         ('lg_approve_time','<',(datetime.datetime.now()-datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"))])
        for item3 in sas:
            customs_id_list3.append(item3.customs_id)
        return customs_id_list3

    # 暂存出入库单
    @api.multi
    def sas_send_to_customs_save(self, record):
        # for sas_id in self.ids:
        #     sas=self.env["iac.customs.sas.header"].browse(sas_id)
        #     if not (sas.state == 'lg_approved' or sas.state=='interface_submit_fail'):
        #         raise UserError('只有lg_approved或interface_submit_fail状态的出入库单,才可以推送海关系统')
        print record.state
        if not (record.state == 'lg_approved' or record.state == 'interface_submit_fail'):
            raise UserError('只有lg_approved或interface_submit_fail状态的出入库单,才可以推送海关系统')

        # for sas_id in self.ids:
        #     sas=self.env["iac.customs.sas.header"].browse(sas_id)
        # sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": record.id,
            "biz_object_id": record.id,
            "odoo_key": record.id
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_001', vals)
            if rpc_result:
                customs_id = rpc_json_data.get("rpc_callback_data").get("Document").get("customs_id")
                record.write({'state': 'interface_submit_success', 'customs_id': customs_id})
                record.env.cr.commit()
                # for sas_stock_line in sas.sas_stock_line_ids:
                #     # print sas_stock_line.id
                #     vals = {
                #         'customs_doc_type':'sas_stock',
                #         'customs_direction':sas.stock_typecd,
                #         'sas_stock_id':sas_id,
                #         'sas_stock_line_id':sas_stock_line.id,
                #         'action':'Call customs interface create SAS stock success'
                #     }
                #     self.env['iac.customs.action.history'].create(vals)
                #     self.env.cr.commit()
            else:
                # msg = exception_log[0]['Message']
                msg = exception_log[0]['Message']
                record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
                record.env.cr.commit()
                for sas_stock_line in record.sas_stock_line_ids:
                    # print sas_stock_line.id
                    vals = {
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.id,
                        'sas_stock_line_id': sas_stock_line.id,
                        'action': 'Call customs interface create SAS stock failed',
                        'iac_write_date': datetime.datetime.now(),
                        'iac_write_uid': self._uid,
                    }
                    hty_obj = self.env['iac.customs.action.history'].create(vals)
                    hty_obj.env.cr.commit()
                return False
                    # self.env.cr.commit()
                    # r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])
        except:
            traceback.print_exc()
            # return False
            raise UserError('调用海关接口发生异常！')
            # continue
        return True

    # 查询出入库单明细
    #flag 1代表发邮件 0代表不发邮件
    @api.multi
    def sas_send_to_customs_getdata(self, customs_id, model_str,flag):
        sas = self.env[model_str].search([('customs_id', '=', customs_id)])
        sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": customs_id,
            "biz_object_id": customs_id,
            "odoo_key": sequence
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_003', vals)
            if rpc_result:
                material_seqno_dict = {}
                sas_stock_no = rpc_json_data.get("rpc_callback_data").get("Document").get("sasStockNo")
                sas_stock_preent_no = rpc_json_data.get("rpc_callback_data").get("Document").get("sasStockPreentNo")
                centralizeddcltypecd = rpc_json_data.get("rpc_callback_data").get("Document").get("centralizedDclTypecd")
                pass_typecd = rpc_json_data.get("rpc_callback_data").get("Document").get("passTypecd")
                passport_used_typecd = rpc_json_data.get("rpc_callback_data").get("Document").get("passportUsedTypecd")
                stucd = rpc_json_data.get("rpc_callback_data").get("Document").get("stucd")
                emapv_markcd = rpc_json_data.get("rpc_callback_data").get("Document").get("emapvMarkcd")
                # sas_stock_no_line = rpc_json_data.get("rpc_callback_data").get("Document").get('ITEM').get("sasStockNo")

                precentralized_dcl_typecd = rpc_json_data.get("rpc_callback_data").get("Document").get("precentralizedDclTypecd")
                prepass_typecd = rpc_json_data.get("rpc_callback_data").get("Document").get("prepassTypecd")
                prepassportUsedTypecd = rpc_json_data.get("rpc_callback_data").get("Document").get("prepassportUsedTypecd")
                prestucd = rpc_json_data.get("rpc_callback_data").get("Document").get("prestucd")

                opt_status = rpc_json_data.get("rpc_callback_data").get("Document").get("optStatus")
                opt_time = rpc_json_data.get("rpc_callback_data").get("Document").get("opt_time")
                opt_remark = rpc_json_data.get("rpc_callback_data").get("Document").get("opt_remark")
                for item in rpc_json_data.get("rpc_callback_data").get("Document").get("ITEM"):
                    material_seqno_dict[item['gdsMtno']]=item['sasStockSeqNo']
                sas.write(
                    {'state': 'done', 'sas_stock_no': sas_stock_no, 'sas_stock_preent_no': sas_stock_preent_no,
                     'centralizeddcltypecd': centralizeddcltypecd, 'pass_typecd': pass_typecd,
                     'passport_used_typecd': passport_used_typecd, 'stucd': stucd, 'emapv_markcd': emapv_markcd,
                     'precentralized_dcl_typecd': precentralized_dcl_typecd, 'prepass_typecd': prepass_typecd,
                     'prepassportUsedTypecd': prepassportUsedTypecd, 'prestucd': prestucd, 'opt_status': opt_status,
                     'opt_time': opt_time, 'opt_remark': opt_remark})
                # 存明细行对应的采购代码
                buyer_code_list = []
                email_to = ''
                vendor = self.env['iac.vendor.register'].search([('vendor_id', '=', sas.vendor_id.id), ('plant_id', '=', sas.plant_id.id)])
                sales_email = vendor.sales_email
                other_emails = vendor.other_emails
                if sales_email and other_emails:
                    vendor_email = sales_email + ';' + other_emails + ';'
                    email_to += vendor_email
                elif sales_email and not other_emails:
                    vendor_email = sales_email + ';'
                    email_to += vendor_email
                elif not sales_email and other_emails:
                    vendor_email = other_emails + ';'
                    email_to += vendor_email
                # 去res_groups表抓关务角色的id
                lg_id = self.env['res.groups'].search([('name', '=', 'LG users')]).id
                # 根据关务id去res_groups_users_rel表抓所有的user_id
                self._cr.execute("select * from res_groups_users_rel where gid=%s", (lg_id,))
                for item in self.env.cr.dictfetchall():
                    # 去user表抓可用帐号的partner_id
                    user = self.env['res.users'].search([('id', '=', item['uid']), ('active', '=', 't')])
                    if user:
                        partner_id = user.partner_id.id
                        # 根据partner_id去partner_plant_rel表确认是否是当前plant下的关务
                        self._cr.execute("select * from partner_plant_rel where partner_id=%s and plant_id=%s",
                                         (partner_id, sas.plant_id.id))
                        result = self.env.cr.dictfetchall()
                        if result:
                            lg_email = self.env['res.partner'].browse(partner_id).email
                            email_to = email_to + lg_email + ';'
                if model_str == 'iac.customs.sas.header':
                    for sas_stock_line in sas.sas_stock_line_ids:
                        # print sas_stock_line.id
                        if sas_stock_line.gds_mtno in material_seqno_dict.keys():
                            sas_stock_line.write({'rlt_stock_seqno':material_seqno_dict[sas_stock_line.gds_mtno]})
                        buyer_code_list.append(sas_stock_line.part_id.buyer_code_id.buyer_erp_id)
                        sas_stock_line.write({'sas_stock_no': sas_stock_no})
                        vals = {
                            'customs_doc_type': 'sas_stock',
                            'customs_direction': sas.stock_typecd,
                            'sas_stock_id': sas.id,
                            'sas_stock_line_id': sas_stock_line.id,
                            'action': 'Call customs interface create SAS stock success',
                            'customs_doc_no': sas_stock_no
                        }
                        val = {
                            'customs_doc_type': 'sas_stock',
                            'customs_direction': sas.stock_typecd,
                            'sas_stock_id': sas.id,
                            'sas_stock_line_id': sas_stock_line.id,
                            'action': 'Customs interface sync data',
                            'customs_doc_no': sas_stock_no
                        }
                        self.env['iac.customs.action.history'].create(vals)
                        self.env['iac.customs.action.history'].create(val)
                        # self.env.cr.commit()
                    # 采购去重
                    buyer_code_list = list(set(buyer_code_list))
                    for buyer_code in buyer_code_list:
                        self._cr.execute("select rp.email from res_users ru "
                                         "inner join res_partner rp on rp.id = ru.partner_id "
                                         "inner join res_partner_buyer_code_line pbcr on pbcr.partner_id = rp.id "
                                         "inner join buyer_code bc on bc.id = pbcr.buyer_code_id "
                                         "where 1 = 1 and bc.buyer_erp_id = %s", (buyer_code,))
                        for item in self.env.cr.dictfetchall():
                            if item['email']:
                                email_to = email_to + item['email'] + ';'
                    if sas_stock_no and flag == '1':
                        # 查询成功发送邮件
                        self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email_to, '',
                                                                  '出入库单据' + sas_stock_no + '海关系统建立成功',
                                                                  ['出入库单据海关号码', '创建日期', '件数', '毛重', '净重', 'PLANT','VENDOR'],
                                                                  [[sas_stock_no, sas.create_date, str(sas.package_qty),
                                                                    str(sas.gross_wt),str(sas.net_wt), sas.plant_id.plant_code,sas.vendor_id.vendor_code]], 'customs')

                if model_str == 'iac.customs.sas.cancel':
                    sas_header = self.env['iac.customs.sas.header'].browse(sas.customs_sas_header_id.id)
                    sas_header.write({'state': 'cancel'})
                    #如果是作废出库单，需要在对应入库单明细上加回可退数量
                    if sas_header.stock_typecd == 'E':
                        export_sas_line_list = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',sas_header.id)])
                        for export_sas_line in export_sas_line_list:
                            import_sas_line = self.env['iac.customs.sas.line'].browse(export_sas_line.orig_sas_line_id.id)
                            import_sas_line.write({'valid_export_qty':import_sas_line.valid_export_qty+export_sas_line.dcl_qty})
                    for sas_stock_line in sas.sas_stock_line_ids:
                        # print sas_stock_line.id
                        if sas_stock_line.gds_mtno in material_seqno_dict.keys():
                            sas_stock_line.write({'rlt_stock_seqno':material_seqno_dict[sas_stock_line.gds_mtno]})
                        buyer_code_list.append(sas_stock_line.part_id.buyer_code_id.buyer_erp_id)
                        sas_stock_line.write({'sas_stock_no': sas_stock_no})
                        vals = {
                            'customs_doc_type': 'sas_stock',
                            'customs_direction': sas.stock_typecd,
                            'sas_stock_id': sas.customs_sas_header_id.id,
                            'sas_stock_line_id': sas_stock_line.id,
                            'action': 'Call customs interface obsolete SAS stock success',
                            'customs_doc_no': sas_stock_no
                        }
                        self.env['iac.customs.action.history'].create(vals)
                    # 采购去重
                    buyer_code_list = list(set(buyer_code_list))
                    for buyer_code in buyer_code_list:
                        self._cr.execute("select rp.email from res_users ru "
                                         "inner join res_partner rp on rp.id = ru.partner_id "
                                         "inner join res_partner_buyer_code_line pbcr on pbcr.partner_id = rp.id "
                                         "inner join buyer_code bc on bc.id = pbcr.buyer_code_id "
                                         "where 1 = 1 and bc.buyer_erp_id = %s", (buyer_code,))
                        for item in self.env.cr.dictfetchall():
                            if item['email']:
                                email_to = email_to + item['email'] + ';'
                    if sas_stock_no and flag == 1:
                        # 查询成功发送邮件
                        self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email_to, '',
                                                                  '出入库单据' + sas_stock_no + '海关系统取消成功',
                                                                  ['出入库单据海关号码', '创建日期', '件数', '毛重', '净重', 'PLANT','VENDOR'],
                                                                  [[sas_stock_no, sas.create_date, str(sas.package_qty),
                                                                    str(sas.gross_wt),str(sas.net_wt), sas.plant_id.plant_code,sas.vendor_id.vendor_code]], 'customs')


            # else:
            #     if model_str == 'iac.customs.sas.cancel':
            #         sas_header = self.env['iac.customs.sas.header'].browse(sas.customs_sas_header_id.id)
            #         sas_header.write({'state': 'done'})

        except:
            traceback.print_exc()
            # 系统出错发送给内部的邮件
            self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw',
                                                      'Zhang.Pei-Wu@iac.com.tw;Wang.Ningg@iac.com.tw;Jiang.Shier@iac.com.tw',
                                                      '','出入库单据查询失败',['IAC ID', '预存单号', 'Table', 'Message'],
                                                      [[str(sas.id), str(sas.customs_id), model_str, str(traceback.format_exc())]],'customs')

    # 出入库单查询done状态的海关资料的job
    @odoo_env
    @api.multi
    def job_sas_done_send_to_customs_getdata(self):
        header_done_list = self.get_sas_header_data_done()
        # header_submit_list = self.get_sas_header_data_submit()
        # cancel_submit_list = self.get_sas_cancel_data_submit()
        if header_done_list:
            for customs_id in header_done_list:
                self.sas_send_to_customs_getdata(customs_id, 'iac.customs.sas.header','0')
                # if header_submit_list:
                #     for customs_id2 in header_submit_list:
                #         self.sas_send_to_customs_getdata(customs_id2, 'iac.customs.sas.header')
                # if cancel_submit_list:
                #     for customs_id3 in cancel_submit_list:
                #         self.sas_send_to_customs_getdata(customs_id3, 'iac.customs.sas.cancel')

    # 出入库单查询推送海关成功状态的海关资料的job
    @odoo_env
    @api.multi
    def job_sas_submit_send_to_customs_getdata(self):
        # header_done_list = self.get_sas_header_data_done()
        header_submit_list = self.get_sas_header_data_submit()
        cancel_submit_list = self.get_sas_cancel_data_submit()
        # if header_done_list:
        #     for customs_id in header_done_list:
        #         self.sas_send_to_customs_getdata(customs_id, 'iac.customs.sas.header')
        if header_submit_list:
            for customs_id2 in header_submit_list:
                self.sas_send_to_customs_getdata(customs_id2, 'iac.customs.sas.header','1')
        if cancel_submit_list:
            for customs_id3 in cancel_submit_list:
                self.sas_send_to_customs_getdata(customs_id3, 'iac.customs.sas.cancel','1')

class IacCustomsUnitMaster(models.Model):
    _name = 'iac.customs.unit.master'
    _table = "iac_customs_unit_master"
    _rec_name = 'unit_name'
    _order = 'id desc'

    unitcd = fields.Char(string='Unit code')
    unit_name = fields.Char(string='Unit name')

class IacCustomsSasLine(models.Model):
    """ 出入库单明细表 """
    _name = "iac.customs.sas.line"
    _table = "iac_customs_sas_line"
    _order = 'id desc'

    sas_stock_no = fields.Char(string=u'出入库单编号')
    sas_stock_seqno = fields.Integer(string=u'明细序号')
    chg_tms_cnt = fields.Integer(string=u'变更次数')
    # sas_dcl_no = fields.Char(string=u'申报表编号')
    sas_dcl_seqno = fields.Integer(string=u'申报表序号')
    oriact_gds_seqno = fields.Integer(string=u'备案序号')
    gds_mtno = fields.Char(string=u'商品料号')
    gdecd = fields.Char(string=u'商品编码')
    gds_nm = fields.Char(string=u'商品名称')
    gds_spcf_model_desc = fields.Char(string=u'规格型号')
    dcl_unitcd = fields.Char(string=u'申报计量单位')
    lawf_unitcd = fields.Char(string=u'法定计量单位')
    secd_lawf_unitcd = fields.Char(string=u'第二法定计量单位')
    natcd = fields.Char(string=u'原产国(地区)')
    destination_natcd = fields.Char(string=u'最终目的国（地区）')
    dcl_uprc_amt = fields.Float(string=u'申报单价',digits=(25,4))
    dcl_total_amt = fields.Float(string=u'申报总价',digits=(25,2))
    dcl_currcd = fields.Char(string=u'币制')
    lawf_qty = fields.Float(string=u'法定数量',digits=(19,5))
    secd_lawf_qty = fields.Float(string=u'第二法定数量',digits=(19,5))
    dcl_qty = fields.Float(string=u'申报数量',digits=(19,5))
    lvyrlf_modecd = fields.Char(string=u'征免方式')
    usetocod = fields.Char(string=u'备注')
    part_id = fields.Many2one('material.master', string=u'料号ID', index=True)
    sas_stock_id = fields.Many2one('iac.customs.sas.header', string=u'出入库单header ID', index=True)
    customs_country_id = fields.Many2one('iac.customs.country.list', string=u'海关国家ID', index=True)
    customs_currency_id = fields.Many2one('iac.customs.currency.list', string=u'海关币别ID', index=True)
    mm_approver_id = fields.Many2one('res.users', string=u'采购审核人员ID', index=True)
    mm_approve_time = fields.Datetime(string=u'采购审核时间')
    state = fields.Selection([("wait_mm_approve", u"待采购确认"),
                              ("wait_lg_approve", u"待关务确认"),
                              ("mm_reject", u"采购拒绝")], string=u"状态")
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    orig_sas_line_id = fields.Many2one('iac.customs.sas.line',string=u'原始出入库单行ID')
    orig_sas_no = fields.Char(string=u'原始出入库单编号')
    open_asn_qty = fields.Integer(string=u'Open Asn数量')
    # valid_export_qty = fields.Float(string=u'入库单可退数量',compute='_compute_valid_export_qty',digits=(19,5))
    valid_export_qty = fields.Float(string=u'入库单可退数量',digits=(19,5))
    sas_dcl_line_id = fields.Many2one('iac.customs.sas.declare.line', string=u'业务申报表行id', index=True)
    sas_cancel_line_id = fields.Many2one('iac.customs.sas.cancel',string=u'对应的cancel item id', index=True)
    rlt_stock_seqno = fields.Integer(string=u'关联商品序号')
    dcl_unit_id = fields.Many2one('iac.customs.unit.master',string=u'申报计量单位ID',index=True)
    lawf_unit_id = fields.Many2one('iac.customs.unit.master',string=u'法定计量单位ID',index=True)
    secd_lawf_unit_id = fields.Many2one('iac.customs.unit.master',string=u'第二法定计量单位ID',index=True)
    buyer_code_id = fields.Many2one('buyer.code',string='buyer code id')


class IacCustomsSasLineInherit(models.Model):
    _inherit = 'iac.customs.sas.line'
    _name = 'iac.customs.sas.line.inherit'
    _table = 'iac_customs_sas_line'

    sas_stock_id = fields.Many2one('iac.customs.sas.header.inherit', string=u'出入库单header ID', index=True)


class IacCustomsSasHeaderInherit(models.Model):
    _inherit = 'iac.customs.sas.header'
    _name = 'iac.customs.sas.header.inherit'
    _table = 'iac_customs_sas_header'

    sas_stock_line_ids = fields.One2many('iac.customs.sas.line.inherit', 'sas_stock_id', string=u'出入库单line ID', index=True)

    def write(self, vals):
        """ 重写write方法，用于buyer和vendor修改备注的校验 """

        for item in self.env.user.groups_id:
            if item.name in ['LG users','Buyer','External vendor']:

                # 截取header备注栏位的前四个字符，先去掉空格,变大写
                storage_location = "".join(vals['usetocod'].split())[0:4].upper()
                customs_vs_sl_obj = self.env['iac.storage.location.address'].search(
                                                    [('storage_location', '=', storage_location),
                                                     ('plant', '=', self.plant_id.plant_code)])

                if not customs_vs_sl_obj:
                    raise exceptions.ValidationError(u'备注栏前四位讯息错误，请填写送货仓别代码(SW01或SW06)，一张入库单只可指定一个仓别代码！')

                else:
                    try:
                        # 调用父类方法写入storage_location和usetocod
                        result = super(IacCustomsSasHeaderInherit,self).write({'storage_location_id':customs_vs_sl_obj.id,
                                                                               'usetocod': "".join(vals['usetocod'].split())})
                        # 记录修改备注的log
                        customs_no_lambda = lambda r:r if self.sas_stock_no else ''
                        self.env['iac.customs.action.history'].create({
                            'customs_doc_no': customs_no_lambda(self.sas_stock_no),
                            'customs_doc_type': 'sas_stock',
                            'sas_stock_id': self.id,
                            'action': '%s Revise remarks'%item.name,
                            'iac_write_uid': self._uid,
                            'iac_write_date': datetime.datetime.now(),
                        })
                        return result
                    except:
                        self.env.cr.rollback()
                        raise exceptions.ValidationError(traceback.format_exc())

        # print vals['usetocod'],self.plant_id.plant_code

    @api.multi
    def button_to_cancel(self):
        """
        vendor作废出入库单
        :return:
        """
        print self.env.user.vendor_id.id
        for item in self.env.user.groups_id:
            if item.name == 'LG users':
                raise exceptions.ValidationError(u'作废按钮只能Vendor操作！')
            elif item.name == 'Buyer':
                raise exceptions.ValidationError(u'作废按钮只能Vendor操作！')
            elif item.name == 'External vendor':
                for record in self:
                    if record.state not in ['done','mm_reject','lg_reject']:
                        raise exceptions.ValidationError(u'当前只能作废状态为"采购退件","关务退件","done"的资料，请重新选择!')
                    elif record.state in ['mm_reject','lg_reject']:
                        # 检查出入库单是否绑定核放单,入库单是否已开出库单
                        # godown_obj = self.env['iac.customs.sas.header'].search([('orig_sas_id', '=', record.id)])
                        # if record.pass_port_no:
                        #     raise exceptions.ValidationError(u'出入库单%s已经绑定核放单,请先作废核放单！'%(record.sas_stock_no,))
                        # elif godown_obj:
                        #     raise exceptions.ValidationError(u'入库单%s已经出库单,请先作废出库单！'%(record.sas_stock_no,))
                        # else:
                        try:
                            super(IacCustomsSasHeaderInherit, record).write({
                                'state': 'cancel',
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now()})
                        except:
                            self.env.cr.rollback()
                            raise exceptions.ValidationError(traceback.format_exc())

                    else:
                        # 检查出入库单是否绑定核放单,入库单是否已开出库单
                        godown_obj =self.env['iac.customs.sas.header'].search([('orig_sas_id','=', record.id)])
                        if record.pass_port_no:
                            pass_port_obj = self.env['iac.customs.pass.port.header'].search([('pass_port_no','=', record.pass_port_no)
                                                                                             ,('state','!=','cancel')])
                            if pass_port_obj:
                                raise exceptions.ValidationError(u'出入库单%s已经绑定核放单,请先作废核放单！' % (record.sas_stock_no,))
                        elif godown_obj:
                            raise exceptions.ValidationError(u'入库单%s已经绑定出库单,请先作废出库单！' % (record.sas_stock_no,))
                        elif record.opt_status != '5':
                            raise exceptions.ValidationError(u'入库单%s海关审批状态不是"审核通过"，无需作废！' % (record.sas_stock_no,))
                        try:
                            super(IacCustomsSasHeaderInherit, record).write({
                                'state': 'to_cancel',
                                'dcl_type_cd': '3',
                                # 'state_back': record.state,
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now()})
                            # 将此笔cancel的资料copy到出入库单作废模型中，state改为待关务签核
                            search_cancel_obj = self.env['iac.customs.sas.cancel'].search([('customs_id','=',record.customs_id)])
                            if search_cancel_obj:
                                search_cancel_obj.write({'state':'wait_lg_approve'})
                            else:
                                canc_obj = self.env['iac.customs.sas.cancel'].create({
                                    'sas_stock_no': record.sas_stock_no,
                                    'dcl_type_cd': '3',
                                    'sas_dcl_no': record.sas_dcl_no,
                                    'sas_stock_preent_no': record.sas_stock_preent_no,
                                    'master_cuscd': record.master_cuscd,
                                    'stock_typecd': record.stock_typecd,
                                    'business_typecd': record.business_typecd,
                                    'centralized_dcl_typecd': record.centralized_dcl_typecd,
                                    'dcl_er': record.dcl_er,
                                    'package_qty': record.package_qty,
                                    'gross_wt': record.gross_wt,
                                    'net_wt': record.net_wt,
                                    'pack_type': record.pack_type,
                                    'pass_typecd': record.pass_typecd,
                                    'passport_used_typecd': record.passport_used_typecd,
                                    'stucd': record.stucd,
                                    'emapv_markcd': record.emapv_markcd,
                                    'usetocod': record.usetocod,
                                    'owner_system': record.owner_system,
                                    'rtl_typecd': record.rtl_typecd,
                                    'precentralized_dcl_typecd': record.precentralized_dcl_typecd,
                                    'prepass_typecd': record.prepass_typecd,
                                    'prepassport_used_typecd': record.prepassport_used_typecd,
                                    'prestucd': record.prestucd,
                                    'has_open_asn': record.has_open_asn,
                                    'vendor_id': record.vendor_id.id,
                                    'plant_id': record.plant_id.id,
                                    'lg_approver_id': record.lg_approver_id.id,
                                    'lg_approve_time': record.lg_approve_time,
                                    # 'create_uid': record.create_uid,
                                    'iac_write_uid': record.iac_write_uid,
                                    'iac_write_date': record.iac_write_date,
                                    'orig_sas_id': record.orig_sas_id,
                                    'orig_sas_no': record.orig_sas_no,
                                    'sas_dcl_id': record.sas_dcl_id.id,
                                    'customs_id': record.customs_id,
                                    'org_code': record.org_code,
                                    # 'sas_stock_line_ids': record.sas_stock_line_ids,
                                    'pass_port_id': record.pass_port_id.id,
                                    'pass_port_no': record.pass_port_no,
                                    'state': 'wait_lg_approve',
                                    'customs_sas_header_id': record.id
                                })
                                for sas_stock_line in record.sas_stock_line_ids:
                                    sas_stock_line.write({'sas_cancel_line_id':canc_obj.id})

                                # 记录action
                                self.env['iac.customs.action.history'].create({
                                    'customs_doc_no': record.sas_stock_no,
                                    'customs_doc_type': 'sas_stock',
                                    'customs_direction': record.stock_typecd,
                                    'sas_stock_id': record.id,
                                    'action': 'Vendor obsolete SAS stock',
                                    'iac_write_uid': self._uid,
                                    'iac_write_date': datetime.datetime.now(),
                                })

                        except:
                            self.env.cr.rollback()
                            raise exceptions.ValidationError(traceback.format_exc())

        message = u'作废出入库单成功,出入库单有单号的需待IAC关务审核，无单号的已经作废完成！'
        return self.env['warning_box'].info(title="Message", message=message)


# class IacCustomsSasLine(models.Model):
#     """ 出入库单明细表 """
#     _name = "iac.customs.sas.line"
#     _table = "iac_customs_sas_line"
#     _order = 'id desc'
#
#     sas_stock_no = fields.Char(string=u'出入库单编号')
#     sas_stock_seqno = fields.Integer(string=u'明细序号')
#     chg_tms_cnt = fields.Integer(string=u'变更次数')
#     # sas_dcl_no = fields.Char(string=u'申报表编号')
#     sas_dcl_seqno = fields.Integer(string=u'申报表序号')
#     oriact_gds_seqno = fields.Integer(string=u'备案序号')
#     gds_mtno = fields.Char(string=u'商品料号')
#     gdecd = fields.Char(string=u'商品编码')
#     gds_nm = fields.Char(string=u'商品名称')
#     gds_spcf_model_desc = fields.Char(string=u'规格型号')
#     dcl_unitcd = fields.Char(string=u'申报计量单位')
#     lawf_unitcd = fields.Char(string=u'法定计量单位')
#     secd_lawf_unitcd = fields.Char(string=u'第二法定计量单位')
#     natcd = fields.Char(string=u'原产国(地区)')
#     destination_natcd = fields.Char(string=u'最终目的国（地区）')
#     dcl_uprc_amt = fields.Float(string=u'申报单价',digits=(25,5))
#     dcl_total_amt = fields.Float(string=u'申报总价',digits=(25,2))
#     dcl_currcd = fields.Char(string=u'币制')
#     lawf_qty = fields.Float(string=u'法定数量',digits=(19,5))
#     secd_lawf_qty = fields.Float(string=u'第二法定数量',digits=(19,5))
#     dcl_qty = fields.Float(string=u'申报数量',digits=(19,5))
#     lvyrlf_modecd = fields.Char(string=u'征免方式')
#     usetocod = fields.Char(string=u'备注')
#     part_id = fields.Many2one('material.master', string=u'料号ID', index=True)
#     sas_stock_id = fields.Many2one('iac.customs.sas.header', string=u'出入库单header ID', index=True)
#     customs_country_id = fields.Many2one('iac.customs.country.list', string=u'海关国家ID', index=True)
#     customs_currency_id = fields.Many2one('iac.customs.currency.list', string=u'海关币别ID', index=True)
#     mm_approver_id = fields.Many2one('res.users', string=u'采购审核人员ID', index=True)
#     mm_approve_time = fields.Datetime(string=u'采购审核时间')
#     state = fields.Selection([("wait_mm_approve", u"待采购确认"),
#                               ("wait_lg_approve", u"待关务确认"),
#                               ("mm_reject", u"采购拒绝")], string=u"状态")
#     create_uid = fields.Integer(string='Created by')
#     iac_write_uid = fields.Integer(string='Last Updated by')
#     iac_write_date = fields.Datetime(string='Last Updated on')
#     create_date = fields.Datetime(string='Created on')
#     orig_sas_line_id = fields.Many2one('iac.customs.sas.line',string=u'原始出入库单行ID')
#     orig_sas_no = fields.Char(string=u'原始出入库单编号')
#     open_asn_qty = fields.Integer(string=u'Open Asn数量')
#     # valid_export_qty = fields.Float(string=u'入库单可退数量',compute='_compute_valid_export_qty',digits=(19,5))
#     valid_export_qty = fields.Float(string=u'入库单可退数量',digits=(19,5))
#     sas_dcl_line_id = fields.Many2one('iac.customs.sas.declare.line', string=u'业务申报表行id', index=True)
#     sas_cancel_line_id = fields.Many2one('iac.customs.sas.cancel',string=u'对应的cancel item id', index=True)

    # @api.one
    # @api.depends('sas_stock_id','sas_stock_id.state','sas_stock_id.export_flag')
    # def _compute_valid_export_qty(self):
    #     if self.sas_stock_id.stock_typecd == 'E':
    #         self.valid_export_qty = 0
    #         # 计算对应的入库单可退数量，先找到当前出库单对应的入库单，stock_typecd = I，
    #         # 再找到所有当前入库单对应的出库单，排除掉作废的出库单，求和算出出库单的数量，作为新开出库单时数量的对比
    #         enter_sas_head_id = self.sas_stock_id.orig_sas_id
    #         enter_sas_line_objs = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',enter_sas_head_id)])
    #         dcl_qty = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',enter_sas_head_id),
    #                                                  ('gds_mtno', '=',self.gds_mtno)]).dcl_qty
    #         out_mount = 0
    #         for enter_sas_line_obj in enter_sas_line_objs:
    #             out_sas_line_obj = self.env['iac.customs.sas.line'].search([('orig_sas_line_id','=',enter_sas_line_obj.id)])
    #             if out_sas_line_obj.sas_stock_id.state != 'cancel':
    #                 out_mount += out_sas_line_obj.dcl_qty
    #         self.orig_sas_line_id.valid_export_qty = dcl_qty - out_mount
    #
    #     elif self.sas_stock_id.stock_typecd == 'I' and self.sas_stock_id.state == 'cancel':
    #         self.valid_export_qty = 0
    #
    #     elif self.sas_stock_id.stock_typecd == 'I' and self.sas_stock_id.export_flag==0:
    #         self.valid_export_qty = self.dcl_qty
    #
    #     elif self.sas_stock_id.stock_typecd == 'I' and self.sas_stock_id.export_flag != 0:
    #         return self.valid_export_qty

# class IacCustomsSasAttachment(models.Model):
#     """ 出入库单文件 """
#     _name = "iac.customs.sas.attachment"
#     _table = "iac_customs_sas_attachment"
#     _order = 'id desc'
#
#     create_uid = fields.Integer(string='Created by',index=True)
#     group = fields.Char(string='Group')
#     description = fields.Char(string='Description')
#     expiration_date = fields.Date(string='Expiration Date', required=True)
#     memo = fields.Text(string='Memo', required=True)
#     sas_stock_id = fields.Many2one('iac.customs.sas.header', string=u'出入库单ID', index=True)
#     state = fields.Char(string='Status')
#     write_uid = fields.Integer(string='Last Updated by',index=True)
#     file_id = fields.Many2one('muk_dms.file', string='Attachment File', ondelete='cascade', index=True)
#     write_date = fields.Datetime(string='Last Updated on')
#     active = fields.Boolean(string='Active', required=True)
#     create_date = fields.Datetime(string='Created on')
#     type = fields.Integer(string='Attachment Type', index=True)
#     upload_date = fields.Date(string='Upload Date')
#     approver_id = fields.Integer(string='Approve User', index=True, required=True)
#     change_id = fields.Integer(string='Change id', index=True, required=True)


class IacCustomsCountryList(models.Model):
    """ 海关国家清单 """
    _name = "iac.customs.country.list"
    _table = "iac_customs_country_list"
    _order = 'id desc'

    customs_name = fields.Char(string=u'海关国别中文名')
    country_code = fields.Char(string=u'海关国别代号')
    country_sysb = fields.Char(string=u'海关国别英文名')
    iac_country_id = fields.Many2one('res.country', string=u'IAC国别ID', index=True)


class IacCustomsCurrencyList(models.Model):
    """ 海关币别清单 """
    _name = "iac.customs.currency.list"
    _table = "iac_customs_currency_list"
    _order = 'id desc'

    customs_name = fields.Char(string=u'海关币别中文名')
    currency_code = fields.Char(string=u'海关币别代号')
    currency_sysb = fields.Char(string=u'海关币别英文名')
    iac_currency_id = fields.Many2one('res.currency', string=u'IAC币别ID', index=True)


class IacCustomsSasOpenAsnLine(models.Model):
    """ OPEN ASN 明细记录 """
    _name = "iac.customs.sas.vs.asn"
    _table = "iac_customs_sas_vs_asn"
    _order = 'id desc'

    create_uid = fields.Integer(string='Created by',index=True)
    sas_stock_line_id = fields.Many2one('iac.customs.sas.line',string=u'出入库单行ID', index=True)
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    asn_line_id = fields.Many2one('iac.asn.line',string='ASN item ID', index=True)


class IacCustomsZparameters(models.Model):
    """
    参数配置表
    """
    _name = 'iac.customs.zparameters'
    _table = "iac_customs_zparameters"
    _order = 'id desc'

    plant_code = fields.Char(string=u'工厂')
    para_category = fields.Char(string=u'参数分类')
    para_key_value = fields.Char(string=u'参数KEY值')
    para_description = fields.Char(string=u'参数含义')
    is_default = fields.Boolean(string=u'是否默认')
    valid_flag = fields.Boolean(string=u'是否有效')


class IacCustomsSasDeclare(models.Model):
    """
    业务申报表header
    """
    _name = 'iac.customs.sas.declare'
    _table = "iac_customs_sas_declare"
    _order = 'id desc'

    sas_dcl_no = fields.Char(string=u'申报表编号')
    master_cuscd = fields.Char(string=u'主管关区代码')
    sas_dcl_preent_no = fields.Char(string=u'预录入编号')
    dcl_typecd = fields.Char(string=u'申报类型')
    business_typecd = fields.Char(string=u'业务类型')
    direction_typecd = fields.Char(string=u'货物流向')
    areain_etpsno = fields.Char(string=u'区内企业编码')
    areain_etpsnm = fields.Char(string=u'区内企业名称')
    valid_time = fields.Date(string=u'有效期')
    dcler = fields.Char(string=u'申请人')
    owner_system = fields.Char(string=u'所属系统')
    valid_flag = fields.Boolean(string=u'是否有效')
    plant_id = fields.Many2one('pur.org.data',string='工厂ID', index=True)
    vendor_id = fields.Many2one('iac.vendor',string='vendor ID', index=True)
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    plant_code = fields.Char(string='Plant')
    vendor_code = fields.Char(string='Vendor Code')


class IacCustomsSasDeclareLine(models.Model):
    """
    业务申报表item
    """
    _name = 'iac.customs.sas.declare.line'
    _table = "iac_customs_sas_declare_line"
    _order = 'id desc'

    sas_dcl_no = fields.Char(string=u'申报表编号')
    sas_dcl_seqno = fields.Float(string=u'明细序号',digits=(19,0))
    mtpck_endprd_typecd = fields.Char(string=u'料件成品类型')
    gds_mtno = fields.Char(string=u'商品料号')
    gdecd = fields.Char(string=u'商品编码')
    gds_nm = fields.Char(string=u'商品名称')
    gdss_pcf_model_desc = fields.Char(string=u'规格型号')
    dcl_qty = fields.Float(string=u'数量',digits=(25,5))
    dcl_unitcd = fields.Char(string=u'申报计量单位')
    dcl_uprc_amt = fields.Float(string=u'单价',digits=(25,5))
    dcl_total_amt = fields.Float(string=u'总价',digits=(25,5))
    dcl_currcd = fields.Char(string=u'币制')
    valid_flag = fields.Boolean(string=u'是否有效')
    part_id = fields.Many2one('material.master', string=u'料号ID', index=True)
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    header_id = fields.Many2one('iac.customs.sas.declare',string=u'业务申报表header ID', index=True)
    oriact_gds_seqno = fields.Float(string=u'备案序号')


class IacCustomsHsCode(models.Model):
    """
    HS code对照表
    """
    _name = 'iac.customs.hs.code'
    _table = "iac_customs_hs_code"
    _order = 'id desc'

    hscode = fields.Char(string='HS Code')
    unit_1 = fields.Char(string=u'法定計量單位')
    unit_2 = fields.Char(string=u'法定第二單位')
    factor_1 = fields.Float(string=u'法定計量單位比例因數',digits=(18,6))
    factor_2 = fields.Float(string=u'第二法定計量單位比例因數',digits=(18,6))
    apldat = fields.Date(string='Application Date')
    cdate = fields.Date(string='Date of Customs approval date')
    tax_rate = fields.Float(string='The rate of tax',digits=(18,6))
    l_flag = fields.Char(string='EXPORT LEGAL FLAG')
    il_flag = fields.Char(string='IMPORT LEGAL FLAG')
    c_flag = fields.Char(string='3C FLAG')
    spe_flag = fields.Char(string='SPECIAL FLAG')
    o_flag = fields.Char(string='O Certificate Flag')
    del_flag = fields.Char(string='Odoo deletion flag')


class IacCustomsSasCancel(models.Model):
    """
    出入库单据作废表
    """
    _name = "iac.customs.sas.cancel"
    _table = "iac_customs_sas_cancel"
    _inherit = 'iac.customs.sas.header'
    _order = 'id desc'

    state = fields.Selection([("wait_lg_approve", u"待关务确认"),
                              ('lg_approved', u'关务核准'),
                              ("lg_reject", u"关务拒绝"),
                              ("interface_submit_success", u"推送海关系统成功"),
                              ("interface_submit_fail", u"推送海关系统失败"),
                              ("done", "done")], string=u"出入库单取消状态")
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    customs_sas_header_id = fields.Many2one('iac.customs.sas.header', string='对应出入库单的id')
    sas_stock_line_ids = fields.One2many('iac.customs.sas.line','sas_cancel_line_id',string=u'出入库单line ID', index=True)


class IacCustomsSasHeaderCheckList(models.Model):
    _inherit = 'iac.customs.sas.cancel'
    _name = 'iac.customs.sas.header.check.list'
    _table = 'iac_customs_sas_cancel'

    @api.multi
    def button_to_customs(self):
        """
        关务审核作废出入库单，送签到海关系统
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只能推送状态为"待关务签核"的资料！')
            else:
                try:
                    record.write({
                        'state': 'lg_approved',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                    flag = self.sas_send_to_customs_cancel(record)
                    if flag==False:
                        flag_list.append(flag)
                    his_obj = self.env['iac.customs.action.history'].create({
                        'customs_doc_no': record.sas_stock_no,
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.id,
                        'action': 'LG approve obsolete sas',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now()
                    })
                    head_obj = self.env['iac.customs.sas.header'].browse(record.customs_sas_header_id.id).write({
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                except:
                    self.env.cr.rollback()
                    record.write({
                        'state': 'interface_submit_fail',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now(),
                        'opt_remark': str(traceback.format_exc())
                    })
                    record.env.cr.commit()
                    # raise exceptions.ValidationError(u'送签失败，请重新推送海关系统！')
                    raise exceptions.ValidationError(traceback.format_exc())
        if len(flag_list)>0:
            message = u'送签失败！'
        else:
            message = u'送签成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_reject_cancel_sas(self):
        """
        关务拒绝vendor作废出入库单
        :return:
        """
        for record in self:
            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只能推送状态为"待关务签核"的资料！')
            else:
                try:
                    record.write({
                        'state': 'lg_reject',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                    back_obj = self.env['iac.customs.sas.header'].browse(record.customs_sas_header_id.id)
                    back_obj.write({
                        'state':'done',
                        'dcl_type_cd': '1'
                    })
                    self.env['iac.customs.action.history'].create({
                        'customs_doc_no': record.sas_stock_no,
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.id,
                        'action': 'LG reject obsolete sas',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now()
                    })
                    self.env['iac.customs.sas.header'].search([('id', '=', record.customs_sas_header_id.id)]).write({
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                except:
                    self.env.cr.rollback()
                    raise exceptions.ValidationError(u'退件失败，请重新操作！')

        message = u'退件成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_to_customs_again(self):
        """
        关务重送失败的作废出入库单
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'interface_submit_fail':
                raise exceptions.ValidationError(u'此按钮只能推送状态为"推送海关失败"的资料！')
            else:
                try:
                    # 调用海关出入库单接口
                    record.write({
                         'iac_write_uid': self._uid,
                         'iac_write_date': datetime.datetime.now(),
                         'lg_approver_id': self._uid,
                         'lg_approve_time': datetime.datetime.now()
                     })
                    flag = self.sas_send_to_customs_cancel(record)
                    if flag==False:
                        flag_list.append(flag)
                    self.env['iac.customs.action.history'].create({
                        'customs_doc_no': record.sas_stock_no,
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.id,
                        'action': 'LG approve fail obsolete sas again',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now()
                    })
                    self.env['iac.customs.sas.header'].search([('id', '=', record.customs_sas_header_id.id)]).write({
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                except:
                    self.env.cr.rollback()
                    record.write({
                        'state': 'interface_submit_fail',
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now(),
                        'opt_remark': str(traceback.format_exc())
                    })
                    record.env.cr.commit()
                    icsh_obj = self.env['iac.customs.sas.header'].search([('id', '=', record.customs_sas_header_id.id)]).write({
                        'iac_write_uid': self._uid,
                        'iac_write_date': datetime.datetime.now(),
                        'lg_approver_id': self._uid,
                        'lg_approve_time': datetime.datetime.now()
                    })
                    icsh_obj.env.cr.commit()
                    # raise exceptions.ValidationError(u'重送失败，请重新操作！')
                    raise exceptions.ValidationError(traceback.format_exc())
        if len(flag_list)>0:
            message = u'重送失败！'
        else:
            message = u'重送成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    # 作废出入库单
    @api.multi
    def sas_send_to_customs_cancel(self, record):
        # for sas_id in self.ids:
        #     sas = self.env["iac.customs.sas.cancel"].browse(sas_id)
        #     if not (sas.state == 'lg_approved' or sas.state == 'interface_submit_fail'):
        #         raise UserError('只有lg_approved或interface_submit_fail状态的出入库单,才可以推送海关系统')
        if not (record.state == 'lg_approved' or record.state == 'interface_submit_fail'):
            raise UserError('只有lg_approved或interface_submit_fail状态的出入库单,才可以推送海关系统')

        # for sas_id in self.ids:
        #     sas = self.env["iac.customs.sas.cancel"].browse(sas_id)
        # sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": record.customs_id,
            "biz_object_id": record.customs_id,
            "odoo_key": record.customs_id
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_006', vals)
            if rpc_result:
                # customs_id = rpc_json_data.get("rpc_callback_data").get("Document").get("customs_id")
                record.write({'state': 'interface_submit_success'})
                record.env.cr.commit()
                # sas_header = self.env['iac.customs.sas.header'].browse(record.customs_sas_header_id.id)
                # sas_header.write({'customs_back_id':sas_header.customs_id})
                # sas_header.write({'customs_id':customs_id})
                # for sas_stock_line in sas.sas_stock_line_ids:
                #     # print sas_stock_line.id
                #     vals = {
                #         'customs_doc_type': 'sas_stock',
                #         'customs_direction': sas.stock_typecd,
                #         'sas_stock_id': sas.customs_sas_header_id.id,
                #         'sas_stock_line_id': sas_stock_line.id,
                #         'action': 'Call customs interface create SAS stock success'
                #     }
                #     self.env['iac.customs.action.history'].create(vals)
                #     self.env.cr.commit()
            else:
                # msg = exception_log[0]['Message']
                # sas_header = self.env['iac.customs.sas.header'].browse(record.customs_sas_header_id.id)
                # sas_header.write({'state': 'done'})
                # sas_header.env.cr.commit()
                msg = exception_log[0]['Message']
                record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
                # record.write({'state': 'interface_submit_fail'})
                record.env.cr.commit()
                for sas_stock_line in record.sas_stock_line_ids:
                    # print sas_stock_line.id
                    vals = {
                        'customs_doc_type': 'sas_stock',
                        'customs_direction': record.stock_typecd,
                        'sas_stock_id': record.customs_sas_header_id.id,
                        'sas_stock_line_id': sas_stock_line.id,
                        'action': 'Call customs interface obsolete SAS stock failed'
                    }
                    history_obj = self.env['iac.customs.action.history'].create(vals)
                    history_obj.env.cr.commit()
                return False
                # r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])
        except:
            traceback.print_exc()
            # msg = rpc_json_data.get("rpc_callback_data").get("Message").get("Message")
            # record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
            # record.env.cr.commit()
            raise UserError('调用海关接口发生异常！')
            # continue
        return True


class IacVendorCreateGodownEntry(models.Model):
    """
    vendor上传创建出入库单
    """
    _name = 'iac.vendor.create.godown.entry'
    _order = 'id desc'

    file_name = fields.Char(string='File Name')
    file = fields.Binary(string='File')
    # reference = fields.Char(string='Reference')
    # notice = fields.Char(string='Notice')

    @api.multi
    def vendor_create_entry(self):
        """
        vendor上传建立入库单
        :return:
        """
        # 检查厂商是否set workspace,没做的报错提醒
        for item in self.env.user.groups_id:
            if item.name == 'External vendor':
                if not self.env.user.vendor_id:
                    raise exceptions.ValidationError(u"请先去workspace选择具体vendor code")
        # 校验vendor上传的入库单
        if not self.file:
            raise exceptions.ValidationError(u'请选需要上传的文件！')
        # 打开excel文件
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        # 根据索引确定表
        sheet_obj = excel_obj.sheet_by_index(0)
        # 获取表头表体区域的行数
        r = 9
        lr = 9
        sheet_nrows = sheet_obj.nrows
        while sheet_obj.cell(r, 10).value or sheet_obj.cell(r, 11).value or sheet_obj.cell(r, 12).value or sheet_obj.cell(r, 13).value or sheet_obj.cell(r, 14).value:
            r += 1
            if sheet_obj.cell(lr, 0).value or sheet_obj.cell(lr, 1).value or sheet_obj.cell(lr, 2).value or sheet_obj.cell(lr, 3).value or sheet_obj.cell(lr, 4).value:
                lr += 1
            if r == sheet_nrows:
                break
        rows = r - 9  # 表体行数
        lrows = lr - 9 # 表头行数
        # print rows,lrows

        i = 9
        # t_row = rows
        while sheet_obj.cell(i, 0).value:
            if not sheet_obj.cell(i,1).value or not sheet_obj.cell(i,2).value or not sheet_obj.cell(i,3).value or not sheet_obj.cell(i,4).value or not sheet_obj.cell(i,6).value:
                raise exceptions.ValidationError(u'Excel表头区域第%d行抬头带*的栏位为必填栏位！'%(i+1,))

            plant_obje = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)])
            # 截取header备注栏位的前四个字符，先去掉空格,变大写
            storage_location = "".join(sheet_obj.cell(i, 6).value.split())[0:4].upper()
            customs_vs_sl_obj = self.env['iac.storage.location.address'].search(
                                        [('storage_location', '=', storage_location),
                                         ('plant','=',plant_obje.plant.plant_code)])
            if not customs_vs_sl_obj:
                raise exceptions.ValidationError(u'Excel表头区域第%d行表头区域备注栏前四位讯息错误，请填写送货仓别代码(SW01或SW06)，一张入库单只可指定一个仓别代码！' % (i + 1,))

            # 检查表头是否有对应的表体
            value_flag = 0
            material_list = []
            for y in range(rows):
                print rows,sheet_obj.cell(9+y,10).value,sheet_obj.cell(i, 0).value
                if not sheet_obj.cell(9+y,10).value:
                    raise exceptions.ValidationError(u'Excel表体第%s行的单据序号为空，请修改后重新上传！'%(10+y,))
                elif sheet_obj.cell(9+y,10).value == sheet_obj.cell(i, 0).value:
                    if not sheet_obj.cell(9+y,10).value or not sheet_obj.cell(9+y,11).value or not sheet_obj.cell(9+y,12).value or not sheet_obj.cell(9+y,13).value or not sheet_obj.cell(9+y,14).value or not sheet_obj.cell(9+y,16).value:
                        raise exceptions.ValidationError(u'Excel表体单据序号为%s抬头带*的栏位为必填栏位！' % int(sheet_obj.cell(9+y, 10).value))
                    value_flag+=1
                    # 检查表体中同一个单据序号的商品料号不能重复
                    sheet_y11 = sheet_obj.cell(9 + y, 11).value.replace(' ', '')
                    print self.env.user.vendor_id.id,self.env.user.vendor_id.vendor_code
                    plant_id = self.env['iac.vendor'].search([('id','=',self.env.user.vendor_id.id)]).plant.id
                    plant_objt = self.env['iac.vendor'].search([('id','=',self.env.user.vendor_id.id)]).plant
                    # material_obj = self.env['material.master'].search([('plant_id','=',plant_id),('part_no','=',sheet_y11)])
                    material_id = self.env['material.master'].search([('plant_id','=',plant_id),('part_no','=',sheet_y11)]).id

                    if not material_id:
                        raise exceptions.ValidationError(u'Excel表体第%s行的商品料号%s在%s厂别下不存在，请修改后重新上传！'%(10+y,sheet_y11,plant_objt.plant_code))

                    if sheet_y11 in material_list:
                        raise exceptions.ValidationError(u'Excel表体第%s行的商品料号%s重复，同一张单据内的料号不能重复，请修改后重新上传！' % (10+y, sheet_y11))
                    else:
                        material_list.append(sheet_y11)

                    # 检查国别，币别的有效性
                    if type(sheet_obj.cell(9+y, 12).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行国别栏位不是数字类型，请检查！' % (10+y,))

                    country_obj = self.env['iac.customs.country.list'].search([('country_code','=',int(sheet_obj.cell(9+y, 12).value))])
                    if not country_obj:
                        raise exceptions.ValidationError(u'Excel表体第%s行国别栏位无效，请检查！' % (10+y,))
                    if type(sheet_obj.cell(9+y, 13).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行币别栏位不是数字类型，请检查！' % (10+y))
                    currency_obj = self.env['iac.customs.currency.list'].search([('currency_code','=',int(sheet_obj.cell(9+y, 13).value))])

                    if not currency_obj:
                        raise exceptions.ValidationError(u'Excel表体第%s行币别栏位无效，请检查！' % (10+y,))
                    # 检查总金额的有效性
                    if ',' in str(sheet_obj.cell(9+y, 17).value) or ' ' in str(sheet_obj.cell(9+y, 17).value):
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位不允许带有逗号和空格，请检查！' %(10+y,))
                    elif type(sheet_obj.cell(9+y, 17).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位不是数字类型，请检查！' % (10+y,))

                    elif not str(sheet_obj.cell(9+y, 17).value).endswith('.0') and len(str(sheet_obj.cell(9+y, 17).value).split('.')[1]) != 2 and len(str(sheet_obj.cell(9+y, 17).value).split('.')[1]) != 1:
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位小数位最多两位，请检查！' % (10+y,))

                    # 检查法定数量，第二法定数量，申报数量的有效性
                    if type(sheet_obj.cell(9 + y, 14).value) != float or type(sheet_obj.cell(9+y, 16).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行法定数量栏位和申报数量不是数字类型，请检查！' % (10+y,))
                    if sheet_obj.cell(9 + y, 15).value != "" and type(sheet_obj.cell(9 + y, 15).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行第二法定数量栏位不是数字类型，请检查！' % (10+y,))
                    if int(sheet_obj.cell(9+y, 16).value) <= 0:
                        raise exceptions.ValidationError(u'Excel表体第%s行申报数量必须大于0，请检查！' % (10+y,))

                    # 检查关联业务申报表是否存在
                    declare_header_id = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                    ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                    ('valid_flag', '=', True),
                                                                                    ('direction_typecd', '=','I')])

                    declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_id.id)])

                    if not declare_header_id:
                        raise exceptions.ValidationError(u'Vendor %s 在厂别%s下没有建立业务申报表，请IAC采购联系关务维护厂商资料(海关注册登记号，厂商中文名称)' %(self.env.user.vendor_id.vendor_code,plant_objt.plant_code))

                    if not declare_line_obj:
                        raise exceptions.ValidationError(u'Excel表体第%s行的商品料号%s在业务申报表%s(厂别%s,Vendor%s)中不存在，请IAC采购确认料号是否存在有效单价，是否已备案，并联系关务变更业务申报表！' % (10+y,sheet_y11,declare_header_id.sas_dcl_no,plant_objt.plant_code,self.env.user.vendor_id.vendor_code))
                    # 校验厂商填写的币制是否争正确
                    if declare_line_obj.dcl_currcd != str(int(sheet_obj.cell(9+y, 13).value)):
                        raise exceptions.ValidationError(u'Excel表体第%s行明细资料币制不正确，请与关务联系！' % (10+y,))

                    # 根据法定计量单位和申报计量单位校验法定数量和申报数量
                    sas_dcl_no = declare_line_obj.sas_dcl_no
                    declare_line_record = self.env['iac.customs.sas.declare.line'].search([('sas_dcl_no','=',sas_dcl_no),
                                                                                           ('part_id','=',material_id)])
                    dcl_unitcd = declare_line_record.dcl_unitcd
                    gdecd = declare_line_record.gdecd
                    hs_record = self.env['iac.customs.hs.code'].search([('hscode','=',gdecd)])
                    unit_1 = hs_record.unit_1
                    # 如果法定计量单位和申报计量单位相同时法定数量和申报数量要一致
                    if dcl_unitcd==unit_1 and sheet_obj.cell(9 + y, 14).value!=sheet_obj.cell(9+y, 16).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当法定计量单位和申报计量单位相同时法定数量和申报数量要一致！' % (10+y,))

                    # 根据申报计量单位和第二法定计量单位校验申报数量和第二法定数量
                    unit_2 = hs_record.unit_2
                    if unit_2 and not sheet_obj.cell(9 + y, 15).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当第二法定计量单位不为空时，请填写第二法定数量！' % (10 + y,))
                    if unit_2 and dcl_unitcd==unit_2 and sheet_obj.cell(9 + y, 15).value!=sheet_obj.cell(9+y, 16).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当第二法定计量单位和申报计量单位相同时第二法定数量和申报数量要一致！' % (10+y,))

            if value_flag == 0:
                raise exceptions.ValidationError(u'Excel表头第%d行没有与之对应的表体资料，请检查！'%(i+1,))

            if value_flag > 50:
                raise exceptions.ValidationError(u'Excel表体中相同的单据序号对应的申报笔数不能超过50！')

            # 对件数，毛重净重进行校验
            for x in range(1,5):
                print sheet_obj.cell(i, x).value
                if type(sheet_obj.cell(i, x).value) != float:
                    raise exceptions.ValidationError(u'Excel表头第%d行件数,毛重,净重或者包装种类栏位不是数字类型，请检查后再上传！' % (i+1,))
            sheet_i2 = sheet_obj.cell(i, 2).value
            sheet_i3 = sheet_obj.cell(i, 3).value
            print sheet_i2,sheet_i3
            if sheet_i2 < sheet_i3:
                raise exceptions.ValidationError(u'Excel表头第%d行的净重不能大于毛重！'%(i+1,))
            # 校验包装种类
            zpar_category = self.env['iac.customs.zparameters'].search([('para_category','=','包装种类'),('para_key_value','=',int(sheet_obj.cell(i, 4).value))])
            if not zpar_category:
                raise exceptions.ValidationError(u'Excel表头第%d行的包装种类不正确！'%(i+1,))

            i+=1
            # t_row-=1
            # i-9等于表头的行数就需要break
            if i-9 == lrows:
                break

        # 校验表体要有对应的表头
        header_line_item = []
        for header_line in range(9, 9 + lrows):
            header_line_item.append(sheet_obj.cell(header_line, 0).value)
        if len(header_line_item) != len(set(header_line_item)):
            raise exceptions.ValidationError(u'Excel表头区域的单据序号有重复，请检查！')
        for line in range(9,9+rows):
            line_item = sheet_obj.cell(line, 10).value
            if line_item not in header_line_item:
                raise exceptions.ValidationError(u'Excel表体第%d行没有与之对应的表头资料，请检查表体对应的表头序号是否填写！'%(line+1,))

        # 校验上传的资料ok的情况下，进行表头表体数据库储存，方式选择：储存表头资料同时储存对应的表体资料
        i = 9
        for hed in range(9,9+lrows):
            plant_id = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant.id
            plant_code = self.env['pur.org.data'].search([('id','=',plant_id)]).plant_code
            cw_date = datetime.datetime.now()
            org_code = self.env['iac.customs.zparameters'].search([('para_category','=','组织编号'),
                                                                   ('valid_flag','=','t'),
                                                                   ('plant_code', '=', plant_code)]).para_key_value
            stock_typecd = self.env['iac.customs.zparameters'].search([('para_category','=','出入库单类型'),
                                                                       ('valid_flag', '=', True),
                                                                       ('plant_code', '=', plant_code),
                                                                       ('para_description', '=', '进区')]).para_key_value
            dcl_er = self.env['iac.customs.zparameters'].search([('para_category','=','申请人'),
                                                                       ('valid_flag', '=', True),
                                                                       ('plant_code', '=', plant_code)]).para_key_value

            # 截取header备注栏位的前四个字符，先去掉空格,变大写
            storage_location = "".join(sheet_obj.cell(i, 6).value.split())[0:4].upper()
            customs_vs_sl_obj = self.env['iac.storage.location.address'].search(
                            [('storage_location', '=', storage_location),
                             ('plant', '=', plant_code)])

            hed_vals = {
                'package_qty': sheet_obj.cell(hed,1).value,
                'gross_wt': sheet_obj.cell(hed,2).value,
                'net_wt': sheet_obj.cell(hed,3).value,
                'pack_type': str(int(sheet_obj.cell(hed,4).value)),
                'usetocod': "".join(str(sheet_obj.cell(hed,6).value).split()),
                'dcl_type_cd': '1',
                'dcl_er': str(dcl_er),
                'master_cuscd': 2240,
                'stock_typecd': str(stock_typecd),
                'owner_system': '1',
                'has_open_asn': True,
                'state': 'wait_mm_approve',
                'vendor_id': self.env.user.vendor_id.id,
                'plant_id': plant_id,
                'create_uid': self._uid,
                'iac_write_uid': self._uid,
                # 'create_date': cw_date,
                'iac_write_date': cw_date,
                'rtl_typecd': '1',
                'org_code': org_code,
                'export_flag':0,
                'storage_location_id': customs_vs_sl_obj.id
            }

            hed_flag = 0
            # flag_list = []
            for hed_line in range(9,9+rows):
                line_asn_qty = 0
                try:
                    if sheet_obj.cell(hed_line,10).value == sheet_obj.cell(hed, 0).value and hed_flag == 0:
                        # 根据入库单的line资料关联业务申报表，补充入库单表头的资料,以及写入出入库单line资料
                        material_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line,11).value.replace(' ', ''))]).id
                        buy_code_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).buyer_code_id.id
                        declare_header_obj = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                        ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                        ('valid_flag', '=', True),
                                                                                         ('direction_typecd', '=', 'I')])
                        declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_obj.id)])
                        hed_vals.update({
                            'sas_dcl_no': str(declare_header_obj.sas_dcl_no),
                            'business_typecd': str(declare_header_obj.business_typecd),
                            'sas_dcl_id': declare_header_obj.id,
                        })

                        dec_hed_object = self.env['iac.customs.sas.header'].create(hed_vals)
                        action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                       'customs_direction': 'I',
                                                                       'sas_stock_id': dec_hed_object.id,
                                                                       'action': 'Vendor create SAS stock',
                                                                       'iac_write_uid': self._uid,
                                                                       'iac_write_date': cw_date})

                        hs_obj = self.env['iac.customs.hs.code'].search([('hscode','=',declare_line_obj.gdecd)])
                        lvyrlf_modecd = self.env['iac.customs.zparameters'].search([('para_category','=','征免方式'),
                                                                           ('valid_flag', '=', 't'),
                                                                           ('plant_code', '=', plant_code)]).para_key_value
                        customs_country_id = self.env['iac.customs.country.list'].search([('country_code','=',int(sheet_obj.cell(hed_line,12).value))]).id
                        customs_currency_id = self.env['iac.customs.currency.list'].search([('currency_code','=',int(sheet_obj.cell(hed_line,13).value))]).id
                        dcl_unit_id = self.env['iac.customs.unit.master'].search([('unitcd','=',declare_line_obj.dcl_unitcd)])
                        lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_1)])
                        secd_lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_2)])
                        line_vals = {
                            'sas_stock_seqno': hed_flag+1,
                            'sas_dcl_seqno': declare_line_obj.sas_dcl_seqno,
                            # 'rlt_stock_seqno': 0,
                            # 'sas_dcl_no': declare_line_obj.header_id.sas_dcl_no,
                            'gds_mtno': sheet_obj.cell(hed_line,11).value.replace(' ', ''),
                            'gdecd': declare_line_obj.gdecd,
                            'gds_nm': declare_line_obj.gds_nm,
                            'gds_spcf_model_desc': declare_line_obj.gdss_pcf_model_desc,
                            'dcl_unitcd': declare_line_obj.dcl_unitcd,
                            'lawf_unitcd': hs_obj.unit_1,
                            'secd_lawf_unitcd': hs_obj.unit_2,
                            'natcd': str(int(sheet_obj.cell(hed_line,12).value)),
                            'destination_natcd': '142',
                            'dcl_uprc_amt': sheet_obj.cell(hed_line,17).value/sheet_obj.cell(hed_line,16).value,
                            # 'dcl_total_amt': (declare_line_obj.dcl_uprc_amt)*sheet_obj.cell(hed_line,16).value,
                            'dcl_total_amt': sheet_obj.cell(hed_line,17).value,
                            'dcl_currcd': str(int(sheet_obj.cell(hed_line,13).value)),
                            'lawf_qty': sheet_obj.cell(hed_line,14).value,
                            # 'secd_lawf_qty': sheet_obj.cell(hed_line,15).value,
                            'dcl_qty': sheet_obj.cell(hed_line,16).value,
                            'lvyrlf_modecd': lvyrlf_modecd,
                            'part_id': material_id,
                            'sas_stock_id': dec_hed_object.id,
                            'customs_country_id': customs_country_id,
                            'customs_currency_id': customs_currency_id,
                            'state': 'wait_mm_approve',
                            'create_uid': self._uid,
                            'iac_write_uid': self._uid,
                            'create_date': cw_date,
                            'iac_write_date': cw_date,
                            'sas_dcl_line_id': declare_line_obj.id,
                            'usetocod': sheet_obj.cell(hed_line,18).value,
                            'oriact_gds_seqno': int(declare_line_obj.oriact_gds_seqno),
                            'valid_export_qty': sheet_obj.cell(hed_line,16).value,
                            'dcl_unit_id': dcl_unit_id.id,
                            'lawf_unit_id': lawf_unit_id.id,
                            'secd_lawf_unit_id': secd_lawf_unit_id.id,
                            'buyer_code_id': buy_code_id
                        }
                        if sheet_obj.cell(hed_line,15).value:
                            line_vals.update({'secd_lawf_qty': sheet_obj.cell(hed_line,15).value})
                        dec_line_object = self.env['iac.customs.sas.line'].create(line_vals)
                        # self._cr.execute(""" select sl.sas_stock_no,sl.state,sl.lawf_unitcd,hc.unit_1,sl.secd_lawf_unitcd,hc.unit_2,sl.* from iac_customs_sas_line sl  inner join iac_customs_hs_code hc on hc.hscode = sl.gdecd
                        #                                                 where hc.unit_1 <> sl.lawf_unitcd or hc.unit_2 <> secd_lawf_unitcd """)
                        # resu = self._cr.fetchall()
                        # if resu:
                        #     raise exceptions.ValidationError(u'上传异常，请联系IAC IT处理')
                        # buyer_code_ids.append(dec_line_object.part_id.buyer_code_id.id)
                        # ((0, 0, {"buyer_code_id": object_id.id}))

                        # dec_line_object.env.cr.commit()
                        sas_vs_buy = self.env['iac.customs.sas.header.vs.buyer.code'].search([('header_id', '=', dec_hed_object.id),
                                                                                              ('buyer_code_id', '=', buy_code_id)])
                        if not sas_vs_buy:
                            self.env['iac.customs.sas.header.vs.buyer.code'].create({
                                'header_id': dec_hed_object.id,
                                'buyer_code_id': buy_code_id
                                # 'dele_flag': '0'
                            })
                        plant_obj = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant
                        print self.env.user.vendor_id.vendor_code,plant_obj.plant_code
                        self._cr.execute(""" select al.id, al.asn_qty from iac_asn_line al 
                                        inner join iac_vendor v on v.id = al.vendor_id 
                                        inner join material_master mm on mm.id = al.part_id 
                                        inner join pur_org_data pod on pod.id = al.plant_id 
                                        where pod.plant_code = %s
                                        and v.vendor_code = %s 
                                        and mm.part_no = %s 
                                        and al.asn_qty > 0 
                                        and not exists (  select 1 from (select COALESCE(sum(gr.qty_received),0)
                                         qty from goods_receipts gr where gr.asn_line_id = al.id) t where t.qty > 0 )""",(plant_obj.plant_code,self.env.user.vendor_id.vendor_code,sheet_obj.cell(hed_line,11).value.replace(' ', '')))


                        # self._cr.execute(""" select id, asn_qty from iac_asn_line al where al.plant_code = %s
                        #                         and al.vendor_code_sap = %s
                        #                         and al.part_no = %s
                        #                         and al.asn_qty > 0
                        #                         and not exists (  select 1 from ( select COALESCE(sum(gr.qty_received),0) qty
                        #                         from goods_receipts gr where gr.asn_line_id = al.id) t where t.qty > 0)""",(plant_obj.plant_code,self.env.user.vendor_id.vendor_code,sheet_obj.cell(hed_line,11).value))
                        res = self._cr.fetchall()
                        if res:
                            # line_asn_qty += [res_line[1] for res_line in res]
                            for res_line in res:
                                self.env['iac.customs.sas.vs.asn'].create({
                                    'create_uid': self._uid,
                                    'iac_write_uid': self._uid,
                                    'iac_write_date': cw_date,
                                    'create_date': cw_date,
                                    'asn_line_id': res_line[0],
                                    'sas_stock_line_id': dec_line_object.id
                            })
                                line_asn_qty += res_line[1]
                            if line_asn_qty < sheet_obj.cell(hed_line,16).value:
                                dec_hed_object.write({'has_open_asn': False})
                                dec_line_object.write({"state": 'wait_mm_approve',
                                                       'open_asn_qty': line_asn_qty})

                            else:
                                dec_hed_object.write({'has_open_asn': True})
                                dec_line_object.write({"state": 'wait_mm_approve',
                                                       'open_asn_qty': line_asn_qty})

                        else:
                            dec_hed_object.write({'has_open_asn': False,
                                                  'state': 'wait_mm_approve'})
                            dec_line_object.write({"state": 'wait_mm_approve',
                                                   'open_asn_qty': 0})
                        hed_flag += 1
                        continue

                    if sheet_obj.cell(hed_line, 10).value == sheet_obj.cell(hed, 0).value and hed_flag != 0:
                        material_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).id
                        buy_code_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).buyer_code_id.id
                        lvyrlf_modecd = self.env['iac.customs.zparameters'].search([('para_category', '=', '征免方式'),
                                                                                    ('valid_flag', '=', 't'),
                                                                                    ('plant_code', '=',plant_code)]).para_key_value
                        declare_header_obj = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                         ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                         ('valid_flag', '=', True),
                                                                                         ('direction_typecd', '=', 'I')])
                        declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_obj.id)])
                        hs_obj = self.env['iac.customs.hs.code'].search([('hscode', '=', declare_line_obj.gdecd)])
                        customs_country_id = self.env['iac.customs.country.list'].search([('country_code', '=', int(sheet_obj.cell(hed_line, 12).value))]).id
                        customs_currency_id = self.env['iac.customs.currency.list'].search([('currency_code', '=', int(sheet_obj.cell(hed_line, 13).value))]).id
                        dcl_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', declare_line_obj.dcl_unitcd)])
                        lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_1)])
                        secd_lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_2)])
                        line_vals = {
                            'sas_stock_seqno': hed_flag+1,
                            'sas_dcl_seqno': declare_line_obj.sas_dcl_seqno,
                            # 'rlt_stock_seqno': 0,
                            # 'sas_dcl_no': declare_line_obj.header_id.sas_dcl_no,
                            'gds_mtno': sheet_obj.cell(hed_line, 11).value.replace(' ', ''),
                            'gdecd': declare_line_obj.gdecd,
                            'gds_nm': declare_line_obj.gds_nm,
                            'gds_spcf_model_desc': declare_line_obj.gdss_pcf_model_desc,
                            'dcl_unitcd': declare_line_obj.dcl_unitcd,
                            'lawf_unitcd': hs_obj.unit_1,
                            'secd_lawf_unitcd': hs_obj.unit_2,
                            'natcd': str(int(sheet_obj.cell(hed_line,12).value)),
                            'destination_natcd': '142',
                            'dcl_uprc_amt': sheet_obj.cell(hed_line,17).value/sheet_obj.cell(hed_line,16).value,
                            # 'dcl_total_amt': (declare_line_obj.dcl_uprc_amt)*sheet_obj.cell(hed_line,16).value,
                            'dcl_total_amt': sheet_obj.cell(hed_line,17).value,
                            'dcl_currcd': str(int(sheet_obj.cell(hed_line,13).value)),
                            'lawf_qty': sheet_obj.cell(hed_line, 14).value,
                            # 'secd_lawf_qty': sheet_obj.cell(hed_line, 15).value,
                            'dcl_qty': sheet_obj.cell(hed_line, 16).value,
                            'lvyrlf_modecd': lvyrlf_modecd,
                            'part_id': material_id,
                            'sas_stock_id': dec_hed_object.id,
                            'customs_country_id': customs_country_id,
                            'customs_currency_id': customs_currency_id,
                            'state': 'wait_mm_approve',
                            'create_uid': self._uid,
                            'iac_write_uid': self._uid,
                            'create_date': cw_date,
                            'iac_write_date': cw_date,
                            'sas_dcl_line_id': declare_line_obj.id,
                            'usetocod': sheet_obj.cell(hed_line, 18).value,
                            'oriact_gds_seqno': int(declare_line_obj.oriact_gds_seqno),
                            'valid_export_qty': sheet_obj.cell(hed_line, 16).value,
                            'dcl_unit_id': dcl_unit_id.id,
                            'lawf_unit_id': lawf_unit_id.id,
                            'secd_lawf_unit_id': secd_lawf_unit_id.id,
                            'buyer_code_id': buy_code_id
                        }
                        if sheet_obj.cell(hed_line,15).value:
                            line_vals.update({'secd_lawf_qty': sheet_obj.cell(hed_line,15).value})
                        dec_line_object = self.env['iac.customs.sas.line'].create(line_vals)
                        # self._cr.execute(""" select sl.sas_stock_no,sl.state,sl.lawf_unitcd,hc.unit_1,sl.secd_lawf_unitcd,hc.unit_2,sl.* from iac_customs_sas_line sl  inner join iac_customs_hs_code hc on hc.hscode = sl.gdecd
                        #                                                                         where hc.unit_1 <> sl.lawf_unitcd or hc.unit_2 <> secd_lawf_unitcd """)
                        # resu = self._cr.fetchall()
                        # if resu:
                        #     raise exceptions.ValidationError(u'上传异常，请联系IAC IT处理')
                        # buyer_code_ids.append(dec_line_object.part_id.buyer_code_id.id)
                        sas_vs_buy = self.env['iac.customs.sas.header.vs.buyer.code'].search([('header_id', '=', dec_hed_object.id),
                                                                                              ('buyer_code_id', '=', buy_code_id)])
                        if not sas_vs_buy:
                            self.env['iac.customs.sas.header.vs.buyer.code'].create({
                                'header_id': dec_hed_object.id,
                                'buyer_code_id': buy_code_id
                                # 'dele_flag': '0'
                            })
                        plant_obj = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant
                        self._cr.execute(""" select al.id, al.asn_qty from iac_asn_line al 
                                                                inner join iac_vendor v on v.id = al.vendor_id 
                                                                inner join material_master mm on mm.id = al.part_id 
                                                                inner join pur_org_data pod on pod.id = al.plant_id 
                                                                where pod.plant_code = %s
                                                                and v.vendor_code = %s 
                                                                and mm.part_no = %s 
                                                                and al.asn_qty > 0 
                                                                and not exists (  select 1 from (select COALESCE(sum(gr.qty_received),0)
                                                                 qty from goods_receipts gr where gr.asn_line_id = al.id) t where t.qty > 0 )""",
                                         (plant_obj.plant_code, self.env.user.vendor_id.vendor_code,sheet_obj.cell(hed_line, 11).value.replace(' ', '')))
                        res = self._cr.fetchall()
                        if res:
                            # line_asn_qty += [res_line[1] for res_line in res]
                            for res_line in res:
                                self.env['iac.customs.sas.vs.asn'].create({
                                    'create_uid': self._uid,
                                    'iac_write_uid': self._uid,
                                    'iac_write_date': cw_date,
                                    'create_date': cw_date,
                                    'asn_line_id': res_line[0],
                                    'sas_stock_line_id': dec_line_object.id
                            })
                                line_asn_qty += res_line[1]
                            if line_asn_qty < sheet_obj.cell(hed_line,16).value:
                                dec_hed_object.write({'has_open_asn': False,
                                                      'state':'wait_mm_approve'})
                                dec_line_object.write({"state": 'wait_mm_approve',
                                                       'open_asn_qty': line_asn_qty})

                            else:
                                dec_line_object.write({"state": 'wait_mm_approve',
                                                       'has_open_asn': True,
                                                       'open_asn_qty': line_asn_qty})

                        else:
                            dec_hed_object.write({'has_open_asn': False,
                                                  'state': 'wait_mm_approve'})
                            dec_line_object.write({"state": 'wait_mm_approve',
                                                   'open_asn_qty': 0})
                        hed_flag += 1

                except:
                    self.env.cr.rollback()
                    raise exceptions.ValidationError(u'创建入库单失败，请重新上传！')
            # buyer_code_ids = list(set(buyer_code_ids))
            # dec_hed_object.write({
            #     'buyer_code_ids': [(6,0,buyer_code_ids)]
            # })
            i += 1
        message = u'档案上传成功，%d张入库单建立成功，待IAC审核，请到出入库单清单查看！'%(lrows,)
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def vendor_create_godown(self):
        """
        vendor上传建立出库单
        :return:
        """
        # 检查费厂商是否set workspace,没做的报错提醒
        for item in self.env.user.groups_id:
            if item.name == 'External vendor':
                if not self.env.user.vendor_id:
                    raise exceptions.ValidationError(u"请先去workspace选择具体vendor code")

        # 校验vendor上传的入库单
        if not self.file:
            raise exceptions.ValidationError(u'请选需要上传的文件！')
        # 打开excel文件
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        # 根据索引确定表
        sheet_obj = excel_obj.sheet_by_index(0)

        # 获取表头表体区域的行数
        r = 9
        lr = 9
        sheet_nrows = sheet_obj.nrows
        while sheet_obj.cell(r, 10).value or sheet_obj.cell(r, 11).value or sheet_obj.cell(r, 12).value or sheet_obj.cell(r, 13).value or sheet_obj.cell(r, 14).value:
            r += 1
            if sheet_obj.cell(lr, 0).value or sheet_obj.cell(lr, 1).value or sheet_obj.cell(lr, 2).value or sheet_obj.cell(lr, 3).value or sheet_obj.cell(lr, 4).value:
                lr += 1
            if r == sheet_nrows:
                break
        rows = r - 9  # 表体行数
        lrows = lr - 9  # 表头行数
        # print rows,lrows
        i = 9
        entry_qty_id_list = []
        out_qty_id_list = []
        while sheet_obj.cell(i, 0).value:
            if not sheet_obj.cell(i, 1).value or not sheet_obj.cell(i, 2).value or not sheet_obj.cell(i,3).value or not sheet_obj.cell(i, 4).value or not sheet_obj.cell(i, 5).value:
                raise exceptions.ValidationError(u'Excel表头区域第%d行抬头带*的栏位为必填栏位！' % (i+1,))
            # 检查表头是否有对应的表体
            value_flag = 0
            material_list = []
            for y in range(rows):
                if not sheet_obj.cell(9+y,10).value:
                    raise exceptions.ValidationError(u'Excel表体第%s行的单据序号为空，请修改后重新上传！'%(10+y,))
                elif sheet_obj.cell(9+y, 10).value == sheet_obj.cell(i, 0).value:
                    if not sheet_obj.cell(9+y, 10).value or not sheet_obj.cell(9 + y,11).value or not sheet_obj.cell(9 + y,12).value or not sheet_obj.cell(9 + y, 13).value or not sheet_obj.cell(9 + y, 14).value or not sheet_obj.cell(9 + y, 16).value:
                        raise exceptions.ValidationError(u'Excel表体单据序号为%s抬头带*的栏位为必填栏位！' % int(sheet_obj.cell(9+y, 10).value))
                    value_flag += 1
                    # 检查表体中同一个单据序号的商品料号不能重复
                    sheet_y11 = sheet_obj.cell(9+y, 11).value.replace(' ', '')
                    plant_id = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant.id
                    plant_objt = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant
                    # material_obj = self.env['material.master'].search([('plant_id','=',plant_id),('part_no','=',sheet_y11)])
                    material_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_y11)]).id

                    if not material_id:
                        raise exceptions.ValidationError(u'Excel表体第%s行的商品料号%s在%s厂别下不存在，请修改后重新上传！' % (10 + y, sheet_y11, plant_objt.plant_code))

                    if sheet_y11 in material_list:
                        raise exceptions.ValidationError(u'Excel表体第%s行的商品料号%s重复，同一张单据内的料号不能重复，请修改后重新上传！' % (10+y, sheet_y11))
                    else:
                        material_list.append(sheet_y11)

                    # 检查国别，币别的有效性
                    if type(sheet_obj.cell(9+y, 12).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行国别栏位不是数字类型，请检查！' % (10+y,))
                    country_obj = self.env['iac.customs.country.list'].search([('country_code', '=', int(sheet_obj.cell(9+y, 12).value))])
                    if not country_obj:
                        raise exceptions.ValidationError(u'Excel表体第%s行国别栏位无效，请检查！' % (10+y,))
                    if type(sheet_obj.cell(9+y, 13).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行币别栏位不是数字类型，请检查！' % (10+y,))
                    currency_obj = self.env['iac.customs.currency.list'].search([('currency_code', '=', int(sheet_obj.cell(9+y, 13).value))])
                    if not currency_obj:
                        raise exceptions.ValidationError(u'Excel表体第%s行币别栏位无效，请检查！' % (10+y,))
                    # 检查总金额的有效性
                    if ',' in str(sheet_obj.cell(9 + y, 17).value) or ' ' in str(sheet_obj.cell(9 + y, 17).value):
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位不允许带有逗号和空格，请检查！' % (10 + y,))
                    elif type(sheet_obj.cell(9 + y, 17).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位不是数字类型，请检查！' % (10 + y,))

                    elif not str(sheet_obj.cell(9 + y, 17).value).endswith('.0') and len(str(sheet_obj.cell(9 + y, 17).value).split('.')[1]) != 2 and len(str(sheet_obj.cell(9 + y, 17).value).split('.')[1]) != 1:
                        raise exceptions.ValidationError(u'Excel表体第%s行总金额栏位小数位最多两位，请检查！' % (10 + y,))

                    # 检查法定数量，第二法定数量，申报数量的有效性
                    if type(sheet_obj.cell(9+y, 14).value) != float or type(sheet_obj.cell(9+y, 16).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行法定数量栏位和申报数量不是数字类型，请检查！' % (10+y,))
                    if sheet_obj.cell(9+y, 15).value != "" and type(sheet_obj.cell(9+y, 15).value) != float:
                        raise exceptions.ValidationError(u'Excel表体第%s行第二法定数量栏位不是数字类型，请检查！' % (10+y,))
                    if int(sheet_obj.cell(9+y, 16).value) <= 0:
                        raise exceptions.ValidationError(u'Excel表体第%s行申报数量必须大于0，请检查！' % (10+y,))

                    declare_header_id = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                    ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                    ('valid_flag', '=', True),
                                                                                    ('direction_typecd', '=', 'I')]).id

                    declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_id)])
                    # 校验厂商填写的币制是否争正确
                    if declare_line_obj.dcl_currcd != str(int(sheet_obj.cell(9+y, 13).value)):
                        raise exceptions.ValidationError(u'Excel表体第%s行明细资料币制不正确，请与关务联系！' % (10+y,))
                    # 根据法定计量单位和申报计量单位校验法定数量和申报数量
                    sas_dcl_no = declare_line_obj.sas_dcl_no
                    declare_line_record = self.env['iac.customs.sas.declare.line'].search([('sas_dcl_no', '=', sas_dcl_no),
                                                                                           ('part_id', '=', material_id)])
                    dcl_unitcd = declare_line_record.dcl_unitcd
                    gdecd = declare_line_record.gdecd
                    hs_record = self.env['iac.customs.hs.code'].search([('hscode', '=', gdecd)])
                    unit_1 = hs_record.unit_1
                    # 如果法定计量单位和申报计量单位相同时法定数量和申报数量要一致
                    if dcl_unitcd == unit_1 and sheet_obj.cell(9+y, 14).value != sheet_obj.cell(9+y, 16).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当法定计量单位和申报计量单位相同时法定数量和申报数量要一致！' % (10+y,))

                    # 根据申报计量单位和第二法定计量单位校验申报数量和第二法定数量
                    unit_2 = hs_record.unit_2
                    if unit_2 and not sheet_obj.cell(9 + y, 15).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当第二法定计量单位不为空时，请填写第二法定数量！' % (10 + y,))
                    if unit_2 and dcl_unitcd == unit_2 and sheet_obj.cell(9+y, 15).value != sheet_obj.cell(9+y,16).value:
                        raise exceptions.ValidationError(u'Excel表体第%s行的资料当第二法定计量单位和申报计量单位相同时第二法定数量和申报数量要一致！' % (10+y,))

                    # 检查表体对应的入库单行是否存在，以表头入库单号和料号判定
                    print sheet_obj.cell(i, 5).value,sheet_y11
                    entry_sas_line = self.env['iac.customs.sas.line'].search([('sas_stock_no','=',sheet_obj.cell(i, 5).value),
                                                                              ('gds_mtno','=',sheet_y11)])
                    if not entry_sas_line:
                        raise exceptions.ValidationError(u'Excel第%s行商品料号%s找不到对应的原始入库单据表体明细，请检查！'%(10+y,sheet_y11))

                    # 检查表体对应的入库单行可退数量是否足够，注意一张入库单可开多张出库单，此处求和
                    entry_out_id = int(str(entry_sas_line.sas_stock_id.id)+str(entry_sas_line.id))
                    entry_qty = entry_sas_line.valid_export_qty
                    out_qty = sheet_obj.cell(9+y, 16).value
                    sas_no = sheet_obj.cell(i, 5).value
                    entry_qty_id = [entry_out_id,entry_qty,sheet_y11,sas_no]
                    out_qty_id = [entry_out_id,out_qty,sheet_y11,sas_no]
                    if entry_qty_id not in entry_qty_id_list:
                        entry_qty_id_list.append(entry_qty_id)
                        out_qty_id_list.append(out_qty_id)
                    else:
                        for rid,qty,part_no,no in out_qty_id_list:
                            if rid == entry_out_id:
                                index = out_qty_id_list.index([rid,qty,sheet_y11,sas_no])
                                qty += out_qty
                                out_qty_id_list[index][1] = qty
            if value_flag == 0:
                raise exceptions.ValidationError(u'Excel表头第%d行没有与之对应的表体资料，请检查表头对应的表体单据序号是否填写！' % (i+1,))

            if value_flag > 50:
                raise exceptions.ValidationError(u'Excel表体中相同的单据序号对应的申报笔数不能超过50！')

            # 对件数，毛重净重进行校验
            for x in range(1, 5):
                if type(sheet_obj.cell(i, x).value) != float:
                    raise exceptions.ValidationError(u'Excel表头第%d行件数,毛重,净重或者包装种类栏位不是数字类型，请检查后再上传！' % (i+1,))
            # sheet_i1 = str(int(sheet_obj.cell(i, 1).value)).replace(' ', '')
            sheet_i2 = sheet_obj.cell(i, 2).value
            sheet_i3 = sheet_obj.cell(i, 3).value
            if sheet_i2 < sheet_i3:
                raise exceptions.ValidationError(u'Excel表头第%d行的净重不能大于毛重！' % (i+1))
            # 校验包装种类
            sheet_i4 = int(sheet_obj.cell(i, 4).value)
            zpar_category = self.env['iac.customs.zparameters'].search([('para_category', '=', '包装种类'), ('para_key_value', '=', sheet_i4)])
            if not zpar_category:
                raise exceptions.ValidationError(u'Excel表头第%d行的包装种类不正确！' % (i+1))

            # 检查表头对应的入库单是否存在，状态是已过卡并且未集报
            entry_sas_obj = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',sheet_obj.cell(i, 5).value),
                                                                       ('pass_typecd','=','3'),
                                                                       ('centralized_dcl_typecd','=','1')])
            if not entry_sas_obj:
                raise exceptions.ValidationError(u'Excel表头第%d行对应的原始入库单据号码不正确，请检查！'%(i+1,))

            i += 1
            # i-9等于表头的行数就需要break
            if i - 9 == lrows:
                break
        # 求和后，判断入库单可退数量是否足够
        for rid1, qty1, pn1,no in entry_qty_id_list:
            for rid2,qty2,pn2,no in out_qty_id_list:
                if rid2 == rid1 and qty2 > qty1:
                    raise exceptions.ValidationError(u'商品料号为%s本次出库总数为%d,对应的原始入库单据可退数量为%d，请检查！'%(pn2,qty2,qty1))

        # 校验表体要有对应的表头
        header_line_item = []
        for header_line in range(9, 9 + lrows):
            header_line_item.append(sheet_obj.cell(header_line, 0).value)
        if len(header_line_item) != len(set(header_line_item)):
            raise exceptions.ValidationError(u'Excel表头区域的单据序号有重复，请检查！')
        for line in range(9, 9 + rows):
            line_item = sheet_obj.cell(line, 10).value
            if line_item not in header_line_item:
                raise exceptions.ValidationError(u'Excel表体第%d行没有与之对应的表头资料，请检查表体对应的表头序号是否填写！' % (line+1))

        # 校验资料ok后写入表头表体资料
        i = 9
        for hed in range(9, 9+lrows):
            plant_id = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant.id
            plant_code = self.env['pur.org.data'].search([('id', '=', plant_id)]).plant_code
            cw_date = datetime.datetime.now()
            org_code = self.env['iac.customs.zparameters'].search([('para_category', '=', '组织编号'),
                                                                   ('valid_flag', '=', 't'),
                                                                   ('plant_code', '=', plant_code)]).para_key_value
            stock_typecd = self.env['iac.customs.zparameters'].search([('para_category', '=', '出入库单类型'),
                                                                       ('valid_flag', '=', 't'),
                                                                       ('plant_code', '=', plant_code),
                                                                       ('para_description','=','出区')]).para_key_value
            dcl_er = self.env['iac.customs.zparameters'].search([('para_category', '=', '申请人'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value
            orig_sas_id = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',sheet_obj.cell(hed,5).value)])

            hed_vals = {
                'package_qty': sheet_obj.cell(hed,1).value,
                'gross_wt': sheet_obj.cell(hed,2).value,
                'net_wt': sheet_obj.cell(hed,3).value,
                'pack_type': str(int(sheet_obj.cell(hed,4).value)),
                'orig_sas_id': orig_sas_id.id,
                'orig_sas_no': orig_sas_id.sas_stock_no,
                'usetocod': sheet_obj.cell(hed,6).value,
                'dcl_type_cd': '1',
                'dcl_er': dcl_er,
                'master_cuscd': '2240',
                'stock_typecd': stock_typecd,
                'owner_system': '1',
                'has_open_asn': True,
                'state': 'wait_mm_approve',
                'vendor_id': self.env.user.vendor_id.id,
                'plant_id': plant_id,
                'create_uid': self._uid,
                'iac_write_uid': self._uid,
                'create_date': cw_date,
                'iac_write_date': cw_date,
                'rtl_typecd': '1',
                'org_code': org_code,
            }
            # orig_obj = self.env['iac.customs.sas.header'].search([('id', '=', orig_sas_id.id)])
            if orig_sas_id.export_flag==0:
                orig_sas_id.write({'export_flag': 1})

            hed_flag = 0
            # buyer_code_ids = []
            for hed_line in range(9, 9 + rows):
                try:
                    if sheet_obj.cell(hed_line, 10).value == sheet_obj.cell(hed, 0).value and hed_flag == 0:
                        # 根据入库单的line资料关联业务申报表，补充入库单表头的资料,以及写入出入库单line资料
                        material_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).id
                        buy_code_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).buyer_code_id.id
                        declare_header_obj = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                         ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                         ('valid_flag', '=', True),
                                                                                         ('direction_typecd', '=', 'I')])
                        declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_obj.id)])
                        hed_vals.update({
                            'sas_dcl_no': declare_header_obj.sas_dcl_no,
                            'business_typecd': declare_header_obj.business_typecd,
                            'sas_dcl_id': declare_header_obj.id,
                        })
                        dec_hed_object = self.env['iac.customs.sas.header'].create(hed_vals)
                        # entry_sas_line = self.env['iac.customs.sas.line'].search([('sas_stock_no', '=', sheet_obj.cell(i, 5).value),
                        #                                                           ('gds_mtno', '=', sheet_y11)])

                        action_history_obj = self.env['iac.customs.action.history'].create({'customs_doc_type': 'sas_stock',
                                                                                            'customs_direction': 'E',
                                                                                            'sas_stock_id': dec_hed_object.id,
                                                                                            'action': 'Vendor create SAS stock',
                                                                                            'iac_write_uid': self._uid,
                                                                                            'iac_write_date': cw_date})
                        hs_obj = self.env['iac.customs.hs.code'].search([('hscode', '=', declare_line_obj.gdecd)])
                        lvyrlf_modecd = self.env['iac.customs.zparameters'].search([('para_category', '=', '征免方式'),
                                                                                    ('valid_flag', '=', 't'),
                                                                                    ('plant_code', '=',plant_code)]).para_key_value
                        customs_country_id = self.env['iac.customs.country.list'].search([('country_code', '=', int(sheet_obj.cell(hed_line, 12).value))]).id
                        customs_currency_id = self.env['iac.customs.currency.list'].search([('currency_code', '=', int(sheet_obj.cell(hed_line, 13).value))]).id
                        orig_sas_line_id = self.env['iac.customs.sas.line'].search([('sas_stock_id','=',orig_sas_id.id),
                                                                                    ('gds_mtno','=',sheet_obj.cell(hed_line,11).value.replace(' ', ''))]).id
                        # rlt_stock_seqno = self.env['iac.customs.sas.line'].search([('sas_stock_no','=',sheet_obj.cell(hed,5).value),
                        #                                                            ('part_id','=',material_id)]).rlt_stock_seqno
                        dcl_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', declare_line_obj.dcl_unitcd)])
                        lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_1)])
                        secd_lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_2)])
                        line_vals = {
                            'sas_stock_seqno': hed_flag + 1,
                            'sas_dcl_seqno': declare_line_obj.sas_dcl_seqno,
                            # 'rlt_stock_seqno': rlt_stock_seqno,
                            # 'sas_dcl_no': declare_line_obj.header_id.sas_dcl_no,
                            'gds_mtno': sheet_obj.cell(hed_line, 11).value.replace(' ', ''),
                            'gdecd': declare_line_obj.gdecd,
                            'gds_nm': declare_line_obj.gds_nm,
                            'gds_spcf_model_desc': declare_line_obj.gdss_pcf_model_desc,
                            'dcl_unitcd': declare_line_obj.dcl_unitcd,
                            'lawf_unitcd': hs_obj.unit_1,
                            'secd_lawf_unitcd': hs_obj.unit_2,
                            'natcd': str(int(sheet_obj.cell(hed_line,12).value)),
                            'destination_natcd': '142',
                            'dcl_uprc_amt': sheet_obj.cell(hed_line,17).value/sheet_obj.cell(hed_line,16).value,
                            # 'dcl_total_amt': (declare_line_obj.dcl_uprc_amt)*sheet_obj.cell(hed_line,16).value,
                            'dcl_total_amt': sheet_obj.cell(hed_line,17).value,
                            'dcl_currcd': str(int(sheet_obj.cell(hed_line,13).value)),
                            'lawf_qty': sheet_obj.cell(hed_line, 14).value,
                            # 'secd_lawf_qty': sheet_obj.cell(hed_line, 15).value,
                            'dcl_qty': sheet_obj.cell(hed_line, 16).value,
                            'lvyrlf_modecd': lvyrlf_modecd,
                            'part_id': material_id,
                            'sas_stock_id': dec_hed_object.id,
                            'customs_country_id': customs_country_id,
                            'customs_currency_id': customs_currency_id,
                            'state': 'wait_mm_approve',
                            'create_uid': self._uid,
                            'iac_write_uid': self._uid,
                            'create_date': cw_date,
                            'iac_write_date': cw_date,
                            'sas_dcl_line_id': declare_line_obj.id,
                            'usetocod': sheet_obj.cell(hed_line, 18).value,
                            'oriact_gds_seqno': int(declare_line_obj.oriact_gds_seqno),
                            'orig_sas_line_id': orig_sas_line_id,
                            'orig_sas_no': orig_sas_id.orig_sas_no,
                            'dcl_unit_id': dcl_unit_id.id,
                            'lawf_unit_id': lawf_unit_id.id,
                            'secd_lawf_unit_id': secd_lawf_unit_id.id,
                            'buyer_code_id': buy_code_id
                            # 'mm_approver_id': self._uid,
                            # 'mm_approve_time': cw_date
                        }
                        if sheet_obj.cell(hed_line,15).value:
                            line_vals.update({'secd_lawf_qty': sheet_obj.cell(hed_line,15).value})
                        dec_line_object = self.env['iac.customs.sas.line'].create(line_vals)
                        # self._cr.execute(""" select sl.sas_stock_no,sl.state,sl.lawf_unitcd,hc.unit_1,sl.secd_lawf_unitcd,hc.unit_2,sl.* from iac_customs_sas_line sl  inner join iac_customs_hs_code hc on hc.hscode = sl.gdecd
                        #                                                                         where hc.unit_1 <> sl.lawf_unitcd or hc.unit_2 <> secd_lawf_unitcd """)
                        # resu = self._cr.fetchall()
                        # if resu:
                        #     raise exceptions.ValidationError(u'上传异常，请联系IAC IT处理')
                        sas_vs_buy = self.env['iac.customs.sas.header.vs.buyer.code'].search([('header_id', '=', dec_hed_object.id),
                                                                                              ('buyer_code_id', '=', buy_code_id)])
                        if not sas_vs_buy:
                            self.env['iac.customs.sas.header.vs.buyer.code'].create({
                                'header_id': dec_hed_object.id,
                                'buyer_code_id': buy_code_id
                            })
                        # buyer_code_ids.append(dec_line_object.part_id.buyer_code_id.id)
                        # print dec_line_object.valid_export_qty
                        # aa = dec_line_object.valid_export_qty
                        hed_flag += 1
                        continue

                    if sheet_obj.cell(hed_line, 10).value == sheet_obj.cell(hed, 0).value and hed_flag != 0:
                        material_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).id
                        buy_code_id = self.env['material.master'].search([('plant_id', '=', plant_id), ('part_no', '=', sheet_obj.cell(hed_line, 11).value.replace(' ', ''))]).buyer_code_id.id
                        lvyrlf_modecd = self.env['iac.customs.zparameters'].search([('para_category', '=', '征免方式'),
                                                                                    ('valid_flag', '=', 't'),
                                                                                    ('plant_code', '=',plant_code)]).para_key_value
                        declare_header_obj = self.env['iac.customs.sas.declare'].search([('plant_id', '=', plant_id),
                                                                                         ('vendor_id', '=',self.env.user.vendor_id.id),
                                                                                         ('valid_flag', '=', True),
                                                                                         ('direction_typecd', '=', 'I')])
                        declare_line_obj = self.env['iac.customs.sas.declare.line'].search([('part_id', '=', material_id), ('header_id', '=', declare_header_obj.id)])
                        hs_obj = self.env['iac.customs.hs.code'].search([('hscode', '=', declare_line_obj.gdecd)])
                        customs_country_id = self.env['iac.customs.country.list'].search([('country_code', '=', int(sheet_obj.cell(hed_line, 12).value))]).id
                        customs_currency_id = self.env['iac.customs.currency.list'].search([('currency_code', '=', int(sheet_obj.cell(hed_line, 13).value))]).id
                        # print sheet_obj.cell(hed_line, 5).value
                        sas_hed_obj = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',sheet_obj.cell(hed, 5).value)])
                        orig_sas_line_id = self.env['iac.customs.sas.line'].search([('sas_stock_id', '=', sas_hed_obj.id),
                                                                                    ('gds_mtno', '=',sheet_obj.cell(hed_line,11).value.replace(' ', ''))]).id
                        # rlt_stock_seqno = self.env['iac.customs.sas.line'].search([('sas_stock_no', '=', sheet_obj.cell(hed, 5).value),
                        #                                                            ('part_id', '=', material_id)]).rlt_stock_seqno
                        dcl_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', declare_line_obj.dcl_unitcd)])
                        lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_1)])
                        secd_lawf_unit_id = self.env['iac.customs.unit.master'].search([('unitcd', '=', hs_obj.unit_2)])
                        line_vals = {
                            'sas_stock_seqno': hed_flag + 1,
                            'sas_dcl_seqno': declare_line_obj.sas_dcl_seqno,
                            # 'rlt_stock_seqno': rlt_stock_seqno,
                            # 'sas_dcl_no': declare_line_obj.header_id.sas_dcl_no,
                            'gds_mtno': sheet_obj.cell(hed_line, 11).value.replace(' ', ''),
                            'gdecd': declare_line_obj.gdecd,
                            'gds_nm': declare_line_obj.gds_nm,
                            'gds_spcf_model_desc': declare_line_obj.gdss_pcf_model_desc,
                            'dcl_unitcd': declare_line_obj.dcl_unitcd,
                            'lawf_unitcd': hs_obj.unit_1,
                            'secd_lawf_unitcd': hs_obj.unit_2,
                            'natcd': str(int(sheet_obj.cell(hed_line,12).value)),
                            'destination_natcd': '142',
                            'dcl_uprc_amt': sheet_obj.cell(hed_line,17).value/sheet_obj.cell(hed_line,16).value,
                            # 'dcl_total_amt': (declare_line_obj.dcl_uprc_amt)*sheet_obj.cell(hed_line,16).value,
                            'dcl_total_amt': sheet_obj.cell(hed_line,17).value,
                            'dcl_currcd': str(int(sheet_obj.cell(hed_line,13).value)),
                            'lawf_qty': sheet_obj.cell(hed_line, 14).value,
                            # 'secd_lawf_qty': sheet_obj.cell(hed_line, 15).value,
                            'dcl_qty': sheet_obj.cell(hed_line, 16).value,
                            'lvyrlf_modecd': lvyrlf_modecd,
                            'part_id': material_id,
                            'sas_stock_id': dec_hed_object.id,
                            'customs_country_id': customs_country_id,
                            'customs_currency_id': customs_currency_id,
                            'state': 'wait_mm_approve',
                            'create_uid': self._uid,
                            'iac_write_uid': self._uid,
                            'create_date': cw_date,
                            'iac_write_date': cw_date,
                            'sas_dcl_line_id': declare_line_obj.id,
                            'usetocod': sheet_obj.cell(hed_line, 18).value,
                            'oriact_gds_seqno': int(declare_line_obj.oriact_gds_seqno),
                            'orig_sas_line_id': orig_sas_line_id,
                            'orig_sas_no': orig_sas_id.orig_sas_no,
                            'dcl_unit_id': dcl_unit_id.id,
                            'lawf_unit_id': lawf_unit_id.id,
                            'secd_lawf_unit_id': secd_lawf_unit_id.id,
                            'buyer_code_id': buy_code_id
                        }
                        if sheet_obj.cell(hed_line,15).value:
                            line_vals.update({'secd_lawf_qty': sheet_obj.cell(hed_line,15).value})
                        dec_line_object = self.env['iac.customs.sas.line'].create(line_vals)
                        # self._cr.execute(""" select sl.sas_stock_no,sl.state,sl.lawf_unitcd,hc.unit_1,sl.secd_lawf_unitcd,hc.unit_2,sl.* from iac_customs_sas_line sl  inner join iac_customs_hs_code hc on hc.hscode = sl.gdecd
                        #                                                                         where hc.unit_1 <> sl.lawf_unitcd or hc.unit_2 <> secd_lawf_unitcd """)
                        # resu = self._cr.fetchall()
                        # if resu:
                        #     raise exceptions.ValidationError(u'上传异常，请联系IAC IT处理')
                        # buyer_code_ids.append(dec_line_object.part_id.buyer_code_id.id)
                        sas_vs_buy = self.env['iac.customs.sas.header.vs.buyer.code'].search([('header_id', '=', dec_hed_object.id),
                                                                                              ('buyer_code_id', '=', buy_code_id)])
                        if not sas_vs_buy:
                            self.env['iac.customs.sas.header.vs.buyer.code'].create({
                                'header_id': dec_hed_object.id,
                                'buyer_code_id': buy_code_id
                            })
                        hed_flag += 1

                except:
                    self.env.cr.rollback()
                    raise exceptions.ValidationError(u'创建出库单失败，请重新上传！')
            # dec_hed_object.write({
            #     'buyer_code_ids': [(6, 0, buyer_code_ids)]
            # })
            i+=1

        for rid1, qty1, pn1,no in entry_qty_id_list:
            for rid2, qty2, pn2,no in out_qty_id_list:
                if rid2 == rid1:
                    vaild_sas_obj = self.env['iac.customs.sas.line'].search([('gds_mtno','=',pn2),('sas_stock_no','=',no)])
                    vaild_sas_obj.write({'valid_export_qty':qty1-qty2})
        message = u'档案上传成功，%d张出库单建立成功，待IAC审核，请到出入库单清单查看！'%(lrows,)
        return self.env['warning_box'].info(title="Message", message=message)



    @api.multi
    def action_download_entry_file(self):
        file_dir = self.env["muk_dms.directory"].search([('name', '=', 'file_template')], limit=1, order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template = self.env["muk_dms.file"].search([('filename', '=', '厂商上传入库单模板_v1.1.xlsx')], limit=1,
                                                        order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!' % ("厂商上传入库单模板_v1.1.xlsx",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s' % (file_template.id,),
            'target': 'new',
        }
        return action

    @api.multi
    def action_download_godown_file(self):
        file_dir = self.env["muk_dms.directory"].search([('name', '=', 'file_template')], limit=1, order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template = self.env["muk_dms.file"].search([('filename', '=', '厂商上传出库单模板_v1.1.xlsx')], limit=1,
                                                        order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!' % ("厂商上传出库单模板_v1.1.xlsx",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s' % (file_template.id,),
            'target': 'new',
        }
        return action


class IacCustomsSasHeaderVSBuyerCode(models.Model):

    _name = 'iac.customs.sas.header.vs.buyer.code'

    header_id = fields.Many2one('iac.customs.sas.header',string=u'出入库单header id')
    buyer_code_id = fields.Many2one('buyer.code',string='buyer code id')
    # dele_flag = fields.Char(string=u'删除标志')






































