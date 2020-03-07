# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import traceback
from odoo.odoo_env import odoo_env
import datetime
from odoo import exceptions
from xlrd import open_workbook
import base64


class IacCustomsPassPortHeader(models.Model):
    """ 核放单Header """
    _name = "iac.customs.pass.port.header"
    _table = "iac_customs_pass_port_header"
    _order = 'id desc'

    pass_port_no = fields.Char(string=u'核放单编号')
    chg_tms_cnt = fields.Integer(string=u'变更次数')
    pass_port_typecd = fields.Selection([('1',u'先入区后报关'),
                                         ('2', u'一线一体化进出区'),
                                         ('3', u'二线进出区'),
                                         ('4', u'非报关进出区'),
                                         ('5', u'卡口登记货物'),
                                         ('6', u'空车进出区'),] ,string=u'核放单类型')
    sas_pass_port_preent_no = fields.Char(string=u'预录入编号')
    dcl_typecd = fields.Selection([('1', u'备案'),('2', u'变更'),('3', u'作废')], string=u'申报类型')
    io_typecd = fields.Selection([('I', u'进区'),('E', u'出区')], string=u'进出标志')
    bind_typecd = fields.Selection([('1', u'一车多票'),
                                    ('2', u'一票一车'),
                                    ('3', u'一票多车')], string=u'绑定类型代码')
    master_cuscd = fields.Char(string=u'关区')
    rlt_tb_typecd = fields.Selection([('1', u'核注清单'),
                                    ('2', u'出入库单'),
                                    ('3', u'提运单')], string=u'关联单证类型代码')
    areain_etpsno = fields.Char(string=u'区内企业编码')
    areain_etps_nm = fields.Char(string=u'区内企业名称')
    vehicle_no = fields.Char(string=u'承运车车牌号')
    vehicle_ic_no = fields.Char(string=u'IC卡号(电子车牌）')
    vehicle_wt = fields.Float(string=u'车自重', digits=(19,5))
    vehicle_frame_wt = fields.Float(string=u'车架重', digits=(19,5))
    total_wt = fields.Float(string=u'总重量', digits=(19,5))
    total_gross_wt = fields.Float(string=u'货物总毛重', digits=(19,5))
    total_net_wt = fields.Float(string=u'货物总净重', digits=(19,5))
    dcl_er_conc = fields.Char(string=u'申请人')
    stucd = fields.Selection([('0', u'已申请'),
                              ('1', u'已审批'),
                              ('2', u'已过卡'),
                              ('3', u'已过一卡'),
                              ('4', u'已过二卡'),
                              ('5', u'已删除'),
                              ('6', u'作废')], string=u'状态代码')
    emapv_markcd = fields.Char(string=u'海关审批标志')
    owner_system = fields.Selection([('1', u'特殊区域'),('2', u'保税物流')], string=u'所属系统', default="1")
    rmk = fields.Char(string=u'备注')
    lg_approver_id = fields.Many2one('res.users',string=u'关务审核人员ID',index=True)
    state = fields.Selection([("wait_lg_approve", u"待关务确认"),
                              ("lg_approved",u'关务核准'),
                              ("lg_reject", u"关务拒绝"),
                              ("interface_submit_success", u"推送海关系统成功"),
                              ("interface_submit_fail", u"推送海关系统失败"),
                              ('to_cancel',u'作废中'),
                              ('cancel',u'厂商取消'),
                              ("done", "done")], string=u"状态")
    lg_approve_time = fields.Datetime(string=u'关务审核时间')
    vendor_id = fields.Many2one('iac.vendor', string=u'供应商ID', index=True)
    plant_id = fields.Many2one('pur.org.data', string=u'工厂ID', index=True)
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    customs_id = fields.Char(string=u'海关返回ID', index=True)
    rlt_no = fields.Char(string=u'关联单据号码串')
    org_code = fields.Char(string=u'组织编号')
    pass_time = fields.Datetime(string=u'过卡时间')
    pass_port_line_ids = fields.One2many('iac.customs.pass.port.bind.sas','pass_port_header_id',string='核放单line id')
    sas_header_ids = fields.One2many('iac.customs.sas.header','pass_port_id',string=u'出入库单 IDs')
    opt_status = fields.Selection([("1", u"暂存"),
                                   ("3", u"海关入库"),
                                   ("4", u"海关入库失败"),
                                   ('5', u'审核通过'),
                                   ('6', u'审核拒绝'),
                                   ("17", u"转人工"),
                                   ("18", u"已申报"),
                                   ("50", u"未过卡"),
                                   ("51", u"已过卡"),
                                   ("52", u"拒绝过卡"),
                                   ("53", u"卡口放行"),
                                   ('95', u'作废申报'),
                                   ("96", u"已作废"),
                                   ("99", u"删除"),
                                   ("100", u"海关删除")], string=u"海关审批状态")
    opt_remark = fields.Char(string=u'海关返回信息')
    opt_time = fields.Datetime(string=u'海关审批时间')

    @api.multi
    def button_to_customs(self):
        """
        lg送签核放单到海关系统
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只允许推送状态为"待关务签核"的资料！')
            try:
                record.write({
                    'state': 'lg_approved',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
                # 调用海关接口，更新资料
                flag = self.passport_send_to_customs_save(record)
                if flag == False:
                    flag_list.append(flag)

                # 记录action
                self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG approve create pass port',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
            except:
                self.env.cr.rollback()
                record.write({
                    'state': 'interface_submit_fail',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'opt_remark':str(traceback.format_exc())
                })
                record.env.cr.commit()
                raise exceptions.ValidationError(u'推送海关系统失败，请重新操作！')
        if len(flag_list)>0:
            message = u'推送海关系统失败！'
        else:
            message = u'推送海关系统成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_to_customs_again(self):
        """
        lg重送状态为失败的资料到海关系统
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'interface_submit_fail':
                raise exceptions.ValidationError(u'此按钮只允许推送状态为"推送海关失败"的资料！')
            try:
                record.write({
                    'state': 'lg_approved',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now()
                })
                # 调用海关接口，更新资料
                flag = self.passport_send_to_customs_save(record)
                if flag == False:
                    flag_list.append(flag)
                # 记录action
                self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG approve create pass port again',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })

            except:
                self.env.cr.rollback()
                record.write({
                    'state': 'interface_submit_fail',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'opt_remark': str(traceback.format_exc())
                })
                record.env.cr.commit()
                raise exceptions.ValidationError(u'推送海关系统失败，请重新操作！')

        if len(flag_list)>0:
            message = u'重送海关系统失败！'
        else:
            message = u'重送海关系统成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_reject_passport(self):
        """
        lg审核退件核放单到vendor
        :return:
        """
        for record in self:
            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只允许推送状态为"待关务审核"的资料！')
            try:
                record.write({
                    'state': 'lg_reject',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })

                # 记录action
                self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG reject create pass port',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })

            except:
                self.env.cr.rollback()
                raise exceptions.ValidationError(u'退件失败，请重新操作！')

        message = u'退件成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    # 从核放单header表抓取done状态的资料
    @api.multi
    def get_passport_header_data_done(self):
        customs_id_list = []
        self._cr.execute("select * from iac_customs_pass_port_header where state=%s "
                         "and create_date>=%s and (stucd=%s or (stucd=%s and emapv_markcd=%s ) or stucd is null)",
                         ('done',(datetime.datetime.now() - datetime.timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),'0', '1', '1'))
        for item in self.env.cr.dictfetchall():
            customs_id_list.append(item['customs_id'])
        return customs_id_list

    # 从核放单header表抓取暂存成功状态的资料
    @api.multi
    def get_passport_header_data_submit(self):
        customs_id_list2 = []
        pass_port = self.env["iac.customs.pass.port.header"].search([('state', '=', 'interface_submit_success'),
                                                                     ('lg_approve_time','<',(datetime.datetime.now()-datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"))])
        for item2 in pass_port:
            customs_id_list2.append(item2.customs_id)
        return customs_id_list2

    # 从核放单cancel表抓取暂存成功状态的资料
    @api.multi
    def get_passport_cancel_data_submit(self):
        customs_id_list3 = []
        pass_port = self.env["iac.customs.pass.port.cancel"].search([('state', '=', 'interface_submit_success'),
                                                                     ('lg_approve_time','<',(datetime.datetime.now()-datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"))])
        for item3 in pass_port:
            customs_id_list3.append(item3.customs_id)
        return customs_id_list3

    # 暂存核放单
    def passport_send_to_customs_save(self, record):
        # for passport_id in self.ids:
        #     passport=self.env["iac.customs.pass.port.header"].browse(passport_id)
        #     if not (passport.state == 'lg_approved' or passport.state=='interface_submit_fail'):
        #         raise UserError('只有lg_approved或interface_submit_fail状态的核放单,才可以推送海关系统')
        if not (record.state == 'lg_approved' or record.state == 'interface_submit_fail'):
            raise UserError('只有lg_approved或interface_submit_fail状态的核放单,才可以推送海关系统')

        # for passport_id in self.ids:
        #     passport = self.env["iac.customs.pass.port.header"].browse(passport_id)
        # sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": record.id,
            "biz_object_id": record.id,
            "odoo_key": record.id
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_002', vals)
            if rpc_result:
                customs_id = rpc_json_data.get("rpc_callback_data").get("Document").get("customs_id")
                record.write({'state': 'interface_submit_success', 'customs_id': customs_id})
                record.env.cr.commit()
                # for sas_stock_line in sas.sas_stock_line_ids:
                # print sas_stock_line.id
                # vals = {
                #     'customs_doc_type':'pass_port',
                #     'customs_direction':passport.io_typecd,
                #     'pass_port_id':passport_id,
                #     'action':'Call customs interface create pass port success'
                # }
                # self.env['iac.customs.action.history'].create(vals)
                # self.env.cr.commit()
            else:
                # msg = exception_log[0]['Message']
                msg = exception_log[0]['Message']
                record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
                record.env.cr.commit()
                # for sas_stock_line in sas.sas_stock_line_ids:
                # print sas_stock_line.id
                vals = {
                    'customs_doc_type': 'pass_port',
                    'customs_direction': record.io_typecd,
                    'pass_port_id': record.id,
                    'action': 'Call customs interface create pass port failed'
                }
                hiy_obj = self.env['iac.customs.action.history'].create(vals)
                hiy_obj.env.cr.commit()
                return False
                # self.env.cr.commit()
                # r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])
        except:
            traceback.print_exc()
            # msg = rpc_json_data.get("rpc_callback_data").get("Message").get("Message")
            # record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
            raise UserError('调用海关接口发生异常！')
            # continue
        return True

    # 查询核放单明细
    #flag 1表示发邮件 0表示不发邮件
    @api.multi
    def passport_send_to_customs_getdata(self, customs_id, model_str,flag):
        passport = self.env[model_str].search([('customs_id', '=', customs_id)])
        sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": customs_id,
            "biz_object_id": customs_id,
            "odoo_key": sequence
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_004', vals)
            if rpc_result:
                pass_port_no = rpc_json_data.get("rpc_callback_data").get("Document").get("passportNo")
                sas_pass_port_preent_no = rpc_json_data.get("rpc_callback_data").get("Document").get("sasPassportPreentNo")
                # stucd = rpc_json_data.get("rpc_callback_data").get("Document").get("stucd")
                emapv_markcd = rpc_json_data.get("rpc_callback_data").get("Document").get("emapvMarkcd")
                opt_status = rpc_json_data.get("rpc_callback_data").get("Document").get("optStatus")
                if opt_status == '18':
                    stucd = '0'
                else:
                    stucd = rpc_json_data.get("rpc_callback_data").get("Document").get("stucd")
                opt_time = rpc_json_data.get("rpc_callback_data").get("Document").get("opt_time")
                opt_remark = rpc_json_data.get("rpc_callback_data").get("Document").get("opt_remark")
                vehicle_ic_no = rpc_json_data.get("rpc_callback_data").get("Document").get("vehicleIcNo")
                passport.write({'state': 'done', 'pass_port_no': pass_port_no,
                                'sas_pass_port_preent_no': sas_pass_port_preent_no,
                                'stucd': stucd, 'emapv_markcd': emapv_markcd, 'opt_status': opt_status,
                                'opt_time': opt_time, 'opt_remark': opt_remark, 'vehicle_ic_no': vehicle_ic_no})

                email_to = ''
                vendor = self.env['iac.vendor.register'].search([('vendor_id', '=', passport.vendor_id.id),
                                                                 ('plant_id', '=', passport.plant_id.id)])
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
                                         (partner_id, passport.plant_id.id))
                        result = self.env.cr.dictfetchall()
                        if result:
                            lg_email = self.env['res.partner'].browse(partner_id).email
                            email_to = email_to + lg_email + ';'
                if model_str == 'iac.customs.pass.port.header':
                    for sas_header in passport.sas_header_ids:
                        sas_header.write({'pass_port_no': pass_port_no})
                    vals = {
                        'customs_doc_type': 'pass_port',
                        'customs_direction': passport.io_typecd,
                        'pass_port_id': passport.id,
                        'action': 'Call customs interface create pass port success',
                        'customs_doc_no': pass_port_no
                    }
                    val = {
                        'customs_doc_type': 'pass_port',
                        'customs_direction': passport.io_typecd,
                        'pass_port_id': passport.id,
                        'action': 'Customs interface sync data',
                        'customs_doc_no': pass_port_no
                    }
                    self.env['iac.customs.action.history'].create(vals)
                    self.env['iac.customs.action.history'].create(val)
                    if pass_port_no and flag == '1':
                        # 查询成功发送邮件
                        self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email_to, '',
                                                                  '核放单据' + pass_port_no + '海关系统建立成功',
                                                                  ['核放单据海关号码', '创建日期', '毛重', '净重', 'PLANT','VENDOR'],
                                                                  [[pass_port_no, passport.create_date,str(passport.total_gross_wt),
                                                                    str(passport.total_net_wt), passport.plant_id.plant_code,
                                                                    passport.vendor_id.vendor_code]], 'customs')

                if model_str == 'iac.customs.pass.port.cancel':
                    passport_header = self.env['iac.customs.pass.port.header'].browse(passport.customs_pass_port_header_id.id)
                    passport_header.write({'state': 'cancel'})
                    vals = {
                        'customs_doc_type': 'pass_port',
                        'customs_direction': passport.io_typecd,
                        'pass_port_id': passport.customs_pass_port_header_id.id,
                        'action': 'Call customs interface  obsolete pass port success',
                        'customs_doc_no': pass_port_no
                    }
                    self.env['iac.customs.action.history'].create(vals)
                    if pass_port_no and flag == 1:
                        # 查询成功发送邮件
                        self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw', email_to, '',
                                                                  '核放单据' + pass_port_no + '海关系统取消成功',
                                                                  ['核放单据海关号码', '创建日期', '毛重', '净重', 'PLANT','VENDOR'],
                                                                  [[pass_port_no, passport.create_date,str(passport.total_gross_wt),str(passport.total_net_wt),
                                                                    passport.plant_id.plant_code,passport.vendor_id.vendor_code]], 'customs')

            # else:
            #     if model_str == 'iac.customs.pass.port.cancel':
            #         passport_header = self.env['iac.customs.pass.port.header'].browse(passport.customs_pass_port_header_id.id)
            #         passport_header.write({'state': 'done'})
                    # self.env.cr.commit()
                    # r.message_post(body=u'•SAP API ODOO_ASN_001: %s'%rpc_json_data['Message']['Message'])
        except:
            traceback.print_exc()
            # 系统出错发送给内部的邮件
            self.env['iac.email.pool'].button_to_mail('iac-ep_support@iac.com.tw',
                                                      'Zhang.Pei-Wu@iac.com.tw;Wang.Ningg@iac.com.tw;Jiang.Shier@iac.com.tw',
                                                      '','核放单据查询失败',['IAC ID', '预存单号', 'Table', 'Message'],
                                                      [[str(passport.id), str(passport.customs_id), model_str,str(traceback.format_exc())]],'customs')

    # 核放单查询done状态的海关资料的job
    @odoo_env
    @api.multi
    def job_passport_done_send_to_customs_getdata(self):
        header_done_list = self.get_passport_header_data_done()
        # header_submit_list = self.get_passport_header_data_submit()
        # cancel_submit_list = self.get_passport_cancel_data_submit()
        if header_done_list:
            for customs_id in header_done_list:
                self.passport_send_to_customs_getdata(customs_id, 'iac.customs.pass.port.header','0')
                # if header_submit_list:
                #     for customs_id2 in header_submit_list:
                #         self.passport_send_to_customs_getdata(customs_id2, 'iac.customs.pass.port.header')
                # if cancel_submit_list:
                #     for customs_id3 in cancel_submit_list:
                #         self.passport_send_to_customs_getdata(customs_id3, 'iac.customs.pass.port.cancel')

    # 核放单查询推送海关成功状态的海关资料的job
    @odoo_env
    @api.multi
    def job_passport_submit_send_to_customs_getdata(self):
        # header_done_list = self.get_passport_header_data_done()
        header_submit_list = self.get_passport_header_data_submit()
        cancel_submit_list = self.get_passport_cancel_data_submit()
        # if header_done_list:
        #     for customs_id in header_done_list:
        #         self.passport_send_to_customs_getdata(customs_id, 'iac.customs.pass.port.header')
        if header_submit_list:
            for customs_id2 in header_submit_list:
                self.passport_send_to_customs_getdata(customs_id2, 'iac.customs.pass.port.header','1')
        if cancel_submit_list:
            for customs_id3 in cancel_submit_list:
                self.passport_send_to_customs_getdata(customs_id3, 'iac.customs.pass.port.cancel','1')


class IacCustomsPassPortHeaderInherit(models.Model):
    _inherit = 'iac.customs.pass.port.header'
    _name = 'iac.customs.pass.port.header.inherit'
    _table = 'iac_customs_pass_port_header'

    @api.multi
    def button_to_cancel(self):
        """
        vendor作废核放单
        :return:
        """
        for item in self.env.user.groups_id:
            if item.name == 'LG users':
                raise exceptions.ValidationError(u'作废按钮只能Vendor操作！')
            elif item.name == 'Buyer':
                raise exceptions.ValidationError(u'作废按钮只能Vendor操作！')
            elif item.name == 'External vendor':
                # message_flag = 1
                for record in self:
                    if record.state not in ['done','mm_reject','lg_reject']:
                        raise exceptions.ValidationError(u'当前只能作废状态为"采购退件","关务退件","done"的资料，请重新选择!')
                    elif record.state in ['mm_reject', 'lg_reject']:
                        # message_flag = 0
                        try:
                            record.write({
                                'state': 'cancel',
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now(),
                            })
                            self.env['iac.customs.action.history'].create({
                                'customs_doc_no': record.pass_port_no,
                                'customs_doc_type': 'pass_port',
                                'pass_port_id': record.id,
                                'action': 'Vendor obsolete pass port',
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now(),
                            })
                        except:
                            self.env.cr.rollback()
                            raise exceptions.ValidationError(traceback.format_exc())

                    else:
                        # 检查核放单对否过卡，已经过卡的核放单不可以作废
                        if record.stucd == '2':
                            raise exceptions.ValidationError(u'已过卡的核放单不能作废！')
                        elif record.opt_status != '5':
                            raise exceptions.ValidationError(u'核放單%s海关审批状态不是"审核通过"，无需作废！' % (record.pass_port_no,))
                        try:
                            record.write({
                                'state': 'to_cancel',
                                'dcl_typecd': '3',
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now(),
                            })
                            self.env['iac.customs.action.history'].create({
                                'customs_doc_no': record.pass_port_no,
                                'customs_doc_type': 'pass_port',
                                'pass_port_id': record.id,
                                'action': 'Vendor obsolete pass port',
                                'iac_write_uid': self._uid,
                                'iac_write_date': datetime.datetime.now(),
                            })

                            # 将此笔资料copy到iac.customs.pass.port.cancel模型中
                            search_cancel_obj =self.env['iac.customs.pass.port.cancel'].search([('customs_id','=',record.customs_id)])
                            if search_cancel_obj:
                                search_cancel_obj.write({'state':'wait_lg_approve'})
                            else:
                                canc_obj = self.env['iac.customs.pass.port.cancel'].create({
                                    'pass_port_no': record.pass_port_no,
                                    'chg_tms_cnt': record.chg_tms_cnt,
                                    'pass_port_typecd': record.pass_port_typecd,
                                    'sas_pass_port_preent_no': record.sas_pass_port_preent_no,
                                    'dcl_typecd': record.dcl_typecd,
                                    'io_typecd': record.io_typecd,
                                    'bind_typecd': record.bind_typecd,
                                    'master_cuscd': record.master_cuscd,
                                    'rlt_tb_typecd': record.rlt_tb_typecd,
                                    'areain_etpsno': record.areain_etpsno,
                                    'areain_etps_nm': record.areain_etps_nm,
                                    'vehicle_no': record.vehicle_no,
                                    'vehicle_ic_no': record.vehicle_ic_no,
                                    'vehicle_wt': record.vehicle_wt,
                                    'vehicle_frame_wt': record.vehicle_frame_wt,
                                    'total_wt': record.total_wt,
                                    'total_gross_wt': record.total_gross_wt,
                                    'total_net_wt': record.total_net_wt,
                                    'dcl_er_conc': record.dcl_er_conc,
                                    'stucd': record.stucd,
                                    'emapv_markcd': record.emapv_markcd,
                                    'owner_system': record.owner_system,
                                    'rmk': record.rmk,
                                    'lg_approver_id': record.lg_approver_id.id,
                                    'state': 'wait_lg_approve',
                                    'lg_approve_time': record.lg_approve_time,
                                    'vendor_id': record.vendor_id.id,
                                    'plant_id': record.plant_id.id,
                                    'iac_write_uid': record.iac_write_uid,
                                    'iac_write_date': record.iac_write_date,
                                    'customs_id': record.customs_id,
                                    'rlt_no': record.rlt_no,
                                    'org_code': record.org_code,
                                    # 'pass_port_line_ids': record.pass_port_line_ids,
                                    # 'sas_header_ids': record.sas_header_ids,
                                    'customs_pass_port_header_id': record.id,
                                })
                                for pass_port_line in record.pass_port_line_ids:
                                    pass_port_line.write({
                                        'pass_cancel_line_id':canc_obj.id
                                    })
                                for sas_head_obj in record.sas_header_ids:
                                    sas_head_obj.write({
                                        'pass_cancel_id':canc_obj.id
                                    })

                        except:
                            self.env.cr.rollback()
                            raise exceptions.ValidationError(u'作废核放单失败，请重新操作！')

        message = u'作废出核放單成功,有核放单号的待IAC关务审核后更新海关系统！无核放单号的对应的出入库单已经释放，可以重新用于开立核放单！'
        return self.env['warning_box'].info(title="Message", message=message)



# class IacCustomsPassPortLine(models.Model):
#     """ 核放单明细表 """
#     _name = "iac.customs.pass.port.liner"
#     _table = "iac_customs_pass_port_line"
#     _order = 'id desc'
#
#     pass_port_no = fields.Char(string=u'核放单编号')
#     pass_port_seqno = fields.Char(string=u'明细序号')
#     chg_tms_cnt = fields.Char(string=u'变更次数')
#     gds_mtno = fields.Char(string=u'商品料号')
#     gdecd = fields.Char(string=u'商品编码')
#     gds_nm = fields.Char(string=u'商品名称')
#     gross_wt = fields.Char(string=u'货物毛重')
#     net_wt = fields.Char(string=u'货物净重')
#     rlt_gds_seqno = fields.Char(string=u'关联商品序号')
#     dcl_unitcd = fields.Char(string=u'申报单位')
#     dcl_qty = fields.Char(string=u'申报数量')
#     rmk = fields.Char(string=u'备注')
#     unit_name = fields.Char(string=u'计量名称', readonly=True)
#     part_id = fields.Many2one('material.master',string=u'料号ID',index=True)
#     pass_port_id = fields.Many2one('iac.customs.pass.port.header',string=u'核放单单header ID',index=True)


# class IacCustomsPassPortAttachment(models.Model):
#     """ 核放单文件 """
#     _name = "iac.customs.pass.port.attachment"
#     _table = "iac_customs_pass_port_attachment"
#     _order = 'id desc'
#
#     create_uid = fields.Integer(string='Created by',index=True)
#     group = fields.Char(string='Group')
#     description = fields.Char(string='Description')
#     expiration_date = fields.Date(string='Expiration Date', required=True)
#     memo = fields.Text(string='Memo', required=True)
#     pass_port_id = fields.Many2one('iac.customs.pass.port.header', string=u'核放单ID', index=True)
#     state = fields.Char(string='Status')
#     write_uid = fields.Integer(string='Last Updated by', index=True)
#     file_id = fields.Many2one('muk_dms.file', string='Attachment File', index=True)
#     write_date = fields.Datetime(string='Last Updated on')
#     active = fields.Boolean(string='Last Updated on', required=True)
#     create_date = fields.Datetime(string='Created on')
#     type = fields.Integer(string='Attachment Type', index=True)
#     upload_date = fields.Date(string='Upload Date', index=True)
#     approver_id = fields.Integer(string='Approve User', index=True, required=True)
#     change_id = fields.Integer(string='Change id', index=True, required=True)


class IacCustomsPassPortBindSas(models.Model):
    """
    核放单与出入库单关联表
    """
    _name = "iac.customs.pass.port.bind.sas"
    _table = "iac_customs_pass_port_bind_sas"
    _order = 'id desc'

    pass_port_header_id = fields.Many2one('iac.customs.pass.port.header', string=u'核放单ID', index=True)
    rlt_tb_typecd = fields.Char(string=u'关联单证类型')
    sas_header_id = fields.Many2one('iac.customs.sas.header', string=u'关联单证编号', index=True)
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    pass_cancel_line_id = fields.Many2one('iac.customs.pass.port.cancel',string=u'对应的cancel item id', index=True)


class IacCustomsPassPortCancel(models.Model):
    """
    核放单据作废表
    """
    _name = "iac.customs.pass.port.cancel"
    _table = "iac_customs_pass_port_cancel"
    _inherit = 'iac.customs.pass.port.header'
    _order = 'id desc'

    state = fields.Selection([("wait_lg_approve", u"待关务确认"),
                              ('cancel', u'厂商取消'),
                              ('lg_approved', u'关务核准'),
                              ("lg_reject", u"关务拒绝"),
                              ("interface_submit_success", u"推送海关系统成功"),
                              ("interface_submit_fail", u"推送海关系统失败"),
                              ("done", "done")], string=u"核放单取消状态")
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')
    customs_pass_port_header_id = fields.Many2one('iac.customs.pass.port.header',string=u'核放单Header ID', index=True)
    pass_port_line_ids = fields.One2many('iac.customs.pass.port.bind.sas','pass_cancel_line_id',string='核放单line id')
    sas_header_ids = fields.One2many('iac.customs.sas.header','pass_cancel_id',string=u'出入库单 IDs')


class IacCustomsPassPortCancelLgApproveCheck(models.Model):
    _inherit = 'iac.customs.pass.port.cancel'
    _name = 'iac.customs.pass.port.cancel.lg.approve.check'
    _table = 'iac_customs_pass_port_cancel'

    @api.multi
    def button_to_customs(self):
        """
        关务送签作废的核放单
        :return:
        """
        flag_list = []
        for record in self:

            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只允许推送"待关务确认"的资料，请重新选择！')
            try:
                record.write({
                    'state': 'lg_approved',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
                # call海关接口
                flag = self.passport_send_to_customs_cancel(record)
                if flag==False:
                    flag_list.append(flag)
                # 记录action
                his_obj = self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG approve obsolete pass port',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
                # his_obj.env.cr.commit()

            except:
                self.env.cr.rollback()
                record.write({
                    'state': 'interface_submit_fail',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
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
    def button_reject_cancel_passport(self):
        """
        关务退件作废的核放单到vendor
        :return:
        """
        for record in self:

            if record.state != 'wait_lg_approve':
                raise exceptions.ValidationError(u'此按钮只允许推送"待关务确认"的资料，请重新选择！')
            try:
                record.write({
                    'state': 'lg_reject',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
                back_obj = self.env['iac.customs.pass.port.header'].browse(record.customs_pass_port_header_id.id)
                back_obj.write({
                    'state':'done',
                    'dcl_typecd': '1'
                })
                # 记录action
                self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG reject obsolete pass port',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
            except:
                self.env.cr.rollback()
                raise exceptions.ValidationError(u'退件失败，请重新操作！')

        message = u'退件成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def button_to_customs_again(self):
        """
        失败的作废核放单重送海关系统
        :return:
        """
        flag_list = []
        for record in self:
            if record.state != 'interface_submit_fail':
                raise exceptions.ValidationError(u'此按钮只允许推送状态为"推送海关失败"的资料，请重新选择！')
            try:
                record.write({
                    'state': 'lg_approved',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })
                # call海关接口
                flag = self.passport_send_to_customs_cancel(record)
                if flag==False:
                    flag_list.append(flag)
                self.env['iac.customs.action.history'].create({
                    'customs_doc_no': record.pass_port_no,
                    'customs_doc_type': 'pass_port',
                    'pass_port_id': record.id,
                    'action': 'LG approve obsolete pass port again',
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                })

            except:
                self.env.cr.rollback()
                record.write({
                    'state': 'interface_submit_fail',
                    'lg_approver_id': self._uid,
                    'lg_approve_time': datetime.datetime.now(),
                    'iac_write_uid': self._uid,
                    'iac_write_date': datetime.datetime.now(),
                    'opt_remark': str(traceback.format_exc())
                })
                record.env.cr.commit()
                # raise exceptions.ValidationError(u'推送海关失败，请重新操作！')
                raise exceptions.ValidationError(traceback.format_exc())
        if len(flag_list)>0:
            message = u'重送海关失败！'
        else:
            message = u'重送海关成功！'
        return self.env['warning_box'].info(title="Message", message=message)

    # 作废核放单
    def passport_send_to_customs_cancel(self, record):
        # for passport_id in self.ids:
        #     passport = self.env["iac.customs.pass.port.cancel"].browse(passport_id)
        #     if not (passport.state == 'lg_approved' or passport.state == 'interface_submit_fail'):
        #         raise UserError('只有lg_approved或interface_submit_fail状态的核放单,才可以推送海关系统')
        if not (record.state == 'lg_approved' or record.state == 'interface_submit_fail'):
            raise UserError('只有lg_approved或interface_submit_fail状态的核放单,才可以推送海关系统')

        # for passport_id in self.ids:
        #     passport = self.env["iac.customs.pass.port.cancel"].browse(passport_id)
        # sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        vals = {
            "id": record.customs_id,
            "biz_object_id": record.customs_id,
            "odoo_key": record.customs_id
        }
        try:
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log('ODOO_CUSTOMS_005', vals)
            if rpc_result:
                # customs_id = rpc_json_data.get("rpc_callback_data").get("Document").get("customs_id")
                record.write({'state': 'interface_submit_success'})
                record.env.cr.commit()
                # passport_header = self.env['iac.customs.pass.port.header'].browse(record.customs_pass_port_header_id.id)
                # passport_header.write({'customs_id': customs_id})
                # for sas_stock_line in sas.sas_stock_line_ids:
                # print sas_stock_line.id
                # vals = {
                #     'customs_doc_type':'pass_port',
                #     'customs_direction':passport.io_typecd,
                #     'pass_port_id':passport_id,
                #     'action':'Call customs interface create pass port success'
                # }
                # self.env['iac.customs.action.history'].create(vals)
                # self.env.cr.commit()
            else:
                # msg = exception_log[0]['Message']
                # passport_header = self.env['iac.customs.pass.port.header'].browse(record.customs_pass_port_header_id.id)
                # passport_header.write({'state': 'done'})
                msg = exception_log[0]['Message']
                record.write({'state': 'interface_submit_fail', 'opt_remark': msg})
                record.env.cr.commit()
                # for sas_stock_line in sas.sas_stock_line_ids:
                # print sas_stock_line.id
                vals = {
                    'customs_doc_type': 'pass_port',
                    'customs_direction': record.io_typecd,
                    'pass_port_id': record.customs_pass_port_header_id.id,
                    'action': 'Call customs interface  obsolete pass port failed'
                }
                hsy_obj = self.env['iac.customs.action.history'].create(vals)
                hsy_obj.env.cr.commit()
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


class IacCustomsActionHistory(models.Model):
    """
    海关单据作业历史记录表
    """
    _name = "iac.customs.action.history"
    _table = "iac_customs_action_history"
    _order = 'id desc'

    customs_doc_no = fields.Char(string=u'海关单据编号')
    customs_doc_type = fields.Selection([('sas_stock',u'出入库单据'),('pass_port',u'核放单')],string=u'海关单据类型')
    customs_direction = fields.Selection([('I',u'入库'),('E',u'出库')],string=u'出入库类型')
    sas_stock_id = fields.Integer(string=u'出入库单ID', index=True)
    pass_port_id = fields.Integer(string=u'核放单ID', index=True)
    sas_stock_line_id = fields.Integer(string=u'出入库单行ID', index=True)
    action = fields.Char(string=u'动作')
    create_uid = fields.Integer(string='Created by')
    iac_write_uid = fields.Integer(string='Last Updated by')
    iac_write_date = fields.Datetime(string='Last Updated on')
    create_date = fields.Datetime(string='Created on')


class IacVendorCreateCheckList(models.Model):
    _name = 'iac.vendor.create.check.list'
    _order = 'id desc'

    file_name = fields.Char(string='File Name')
    file = fields.Binary(string='File')

    @api.multi
    def vendor_create_checklist(self):
        """
        vendor上传建立核放单
        :return:
        """
        # 检查厂商是否set workspace,没做的报错提醒
        for item in self.env.user.groups_id:
            if item.name == 'External vendor':
                if not self.env.user.vendor_id:
                    raise exceptions.ValidationError(u'请先去workspace选择具体的vendor code!')
        plant_id = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant.id
        if plant_id != 27:
            raise exceptions.ValidationError(u'请选择厂别CP21！')

        # 检验vendor上传的核放单
        if not self.file:
            raise exceptions.ValidationError(u'请选择需要上传的文件！')

        # 打开excel文件
        excel_obj = open_workbook(file_contents=base64.decodestring(self.file))
        # 根据索引确定表
        sheet_obj = excel_obj.sheet_by_index(0)
        # 获取表头表体区域的行数
        r = 9
        lr = 9
        sheet_nrows = sheet_obj.nrows
        while sheet_obj.cell(r, 10).value or sheet_obj.cell(r, 11).value:
            r += 1
            if sheet_obj.cell(lr, 0).value or sheet_obj.cell(lr, 1).value or sheet_obj.cell(lr, 2).value or sheet_obj.cell(lr, 3).value or sheet_obj.cell(lr, 4).value:
                lr += 1
            if r == sheet_nrows:
                break
        rows = r - 9  # 表体行数
        lrows = lr - 9  # 表头行数
        # print rows,lrows

        i = 9
        while sheet_obj.cell(i, 0).value:
            if not sheet_obj.cell(i, 1).value or not sheet_obj.cell(i, 2).value or not sheet_obj.cell(i,3).value or not sheet_obj.cell(i, 4).value or not sheet_obj.cell(i, 5).value:
                raise exceptions.ValidationError(u'Excel表头区域第%d行抬头带*的栏位为必填栏位！' % (i+1,))

            print sheet_obj.cell(i, 1).value,int(sheet_obj.cell(i, 2).value)
            if sheet_obj.cell(i, 1).value not in ['I','E']:
                raise exceptions.ValidationError(u'Excel表头区域第%d行进出标志栏位必须是I或者E！' % (i+1,))

            if int(sheet_obj.cell(i, 2).value) not in [1,2]:
                raise exceptions.ValidationError(u'Excel表头区域第%d行绑定类型代码必须是1或者2！' % (i+1,))

            if type(sheet_obj.cell(i, 4).value) != float or type(sheet_obj.cell(i, 5).value) != float:
                raise exceptions.ValidationError(u'Excel表头第%d行车自重,车架重栏位不是数字类型，请检查后再上传！' % (i+1))
            # sheet_i1 = str(int(sheet_obj.cell(i, 1).value)).replace(' ', '')
            # sheet_i2 = str(int(sheet_obj.cell(i, 2).value)).replace(' ', '')
            # sheet_i3 = str(int(sheet_obj.cell(i, 3).value)).replace(' ', '')

            # 检查表头是否有对应的表体
            value_flag = 0
            org_no_list = []
            for y in range(rows):
                if not sheet_obj.cell(9+y,10).value:
                    raise exceptions.ValidationError(u'Excel表体第%s行的单据序号为空，请修改后重新上传！'%(10+y,))
                if sheet_obj.cell(9+y, 10).value == sheet_obj.cell(i, 0).value:
                    if not sheet_obj.cell(9+y, 10).value or not sheet_obj.cell(9+y,11).value:
                        raise exceptions.ValidationError(u'Excel表体单据序号为%s抬头带*的栏位为必填栏位！' % int(sheet_obj.cell(9+y, 10).value))
                    value_flag += 1

                    # 检查表体的出入库单编号不能有重复,编号是否存在
                    org_no = sheet_obj.cell(9+y, 11).value.replace(' ', '')
                    if org_no not in org_no_list:
                        org_no_list.append(org_no)
                    else:
                        raise exceptions.ValidationError(u'Excel表体关联单证号码%s重复，请检查之后再上传！' % (sheet_obj.cell(9+y, 11).value,))

                    org_no_obj = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no),('state','=','done'),('opt_status','=','5')])
                    if not org_no_obj:
                        raise exceptions.ValidationError(u'Excel表体关联单证号码%s无效，请检查之后再上传！' % (sheet_obj.cell(9+y, 11).value,))

                    if sheet_obj.cell(i, 1).value != org_no_obj.stock_typecd:
                        raise exceptions.ValidationError(u'Excel表体关联单证号码%s进出区类型与表头进出标志不符，请检查之后再上传！' % (sheet_obj.cell(9+y, 11).value,))

                    if org_no_obj.passport_used_typecd == 3:
                        raise exceptions.ValidationError(u'Excel表体关联单证号码%s已经绑定过核放单，请检查之后再上传！' % (sheet_obj.cell(9+y, 11).value,))
                    # 检查关联单证号是否合法，即是否绑定多核放单
                    # sas_pass_id = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no)]).id
                    # sas_port_obj = self.env['iac.customs.pass.port.bind.sas'].search([('sas_header_id','=',sas_pass_id)])
                    # if sas_port_obj:
                    #     raise exceptions.ValidationError(u'Excel表体关联单证号码%s已经绑定过核放单，请检查之后再上传！' % (sheet_obj.cell(9 + y, 11).value,))

                    sas_head_obj = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no)])
                    # 如果海关审批未通过的出入库单不允许开核放单
                    statu_list = ["暂存","海关入库","海关入库失败","审核通过","审核拒绝","转人工","已申报","作废申报","已作废","删除"]
                    statu_no_list = ['1', '3', '4', '5', '6', '17', '18', '95', '96', '99']
                    status = [statu_list[statu_no_list.index(statu)] for statu in statu_no_list if statu == sas_head_obj.opt_status]
                    # print status[0],str(status[0])
                    if sas_head_obj.opt_status != '5':
                        raise exceptions.ValidationError(u'Excel表体关联单证号码%s海关状态为%s，不允许开立核放单！' % (sheet_obj.cell(9+y, 11).value,str(status[0])))
                    # 判断核放单是否已经绑定出入库单
                    pass_port_org_objs = self.env['iac.customs.pass.port.bind.sas'].search([('sas_header_id','=',sas_head_obj.id)])
                    for pass_port_org_obj in pass_port_org_objs:
                        if pass_port_org_obj and pass_port_org_obj.pass_port_header_id.state != 'cancel':
                            raise exceptions.ValidationError(u'Excel表体关联单证号码%s海关正在审核,如需重新绑定,先cancel流程中绑定关系！' % (sheet_obj.cell(9+y, 11).value,))

            # 判断表头是否有对应表体
            if value_flag == 0:
                raise exceptions.ValidationError(u'Excel表头第%d行没有与之对应的表体资料，请检查表头对应的表体单据序号是否填写！' % (i+1))
            # 如果是一票一车，表体中只能有一张出入库单
            if int(sheet_obj.cell(i, 2).value) == 2 and value_flag != 1:
                raise exceptions.ValidationError(u'Excel表头序号%s的资料是一车一票，表体中只能对应一张出入库单，请检查之后再上传！' % int(sheet_obj.cell(i, 0).value))

            # 如果是一车多票，表体中要有多张出入库单
            if int(sheet_obj.cell(i, 2).value) == 1 and value_flag <= 1:
                raise exceptions.ValidationError(u'Excel表头序号%s的资料是一车多票，表体中必须有多张出入库单，请检查之后再上传！' % int(sheet_obj.cell(i, 0).value))

            # 如果是一票多车就直接报错
            if int(sheet_obj.cell(i, 2).value) == 3:
                raise exceptions.ValidationError(u'Excel表头序号%s的资料不允许一票多车！'% int(sheet_obj.cell(i, 0).value))

            i+=1
            # i-9等于表头的行数就需要break
            if i-9 == lrows:
                break
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

        # 资料校验ok后写入数据库
        i = 9
        for hed in range(9, 9+lrows):
            # org_no = sheet_obj.cell(hed, 11).value.replace(' ', '')
            # try:
            plant_id = self.env['iac.vendor'].search([('id', '=', self.env.user.vendor_id.id)]).plant.id
            plant_code = self.env['pur.org.data'].search([('id', '=', plant_id)]).plant_code
            cw_date = datetime.datetime.now()
            pass_port_typecd = self.env['iac.customs.zparameters'].search([('id','=',8)]).para_key_value
            master_cuscd = self.env['iac.customs.zparameters'].search([('para_category', '=', '关区'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value
            rlt_tb_typecd = self.env['iac.customs.zparameters'].search([('para_category', '=', '关联单证类型'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value
            areain_etpsno = self.env['iac.customs.zparameters'].search([('para_category', '=', '区内企业编码'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value
            areain_etps_nm = self.env['iac.customs.zparameters'].search([('para_category', '=', '区内企业名称'),
                                                                        ('valid_flag', '=', 't'),
                                                                        ('plant_code', '=', plant_code)]).para_key_value
            dcl_er = self.env['iac.customs.zparameters'].search([('para_category', '=', '申请人'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value
            owner_system = self.env['iac.customs.zparameters'].search([('para_category', '=', '所属系统'),
                                                                 ('valid_flag', '=', 't'),
                                                                 ('plant_code', '=', plant_code)]).para_key_value

            org_code = self.env['iac.customs.zparameters'].search([('para_category', '=', '组织编号'),
                                                                   ('valid_flag', '=', 't'),
                                                                   ('plant_code', '=', plant_code)]).para_key_value
            # print sheet_obj.cell(i, 3).value,type(sheet_obj.cell(i, 3).value)
            pass_port_header_vals = {
                'pass_port_typecd': pass_port_typecd,
                'dcl_typecd': '1',
                'io_typecd': sheet_obj.cell(i, 1).value,
                'bind_typecd': str(int(sheet_obj.cell(i, 2).value)),
                'master_cuscd': master_cuscd,
                'rlt_tb_typecd': rlt_tb_typecd,
                'areain_etpsno': areain_etpsno,
                'areain_etps_nm': areain_etps_nm,
                'vehicle_no': sheet_obj.cell(i, 3).value,
                'vehicle_wt': sheet_obj.cell(i, 4).value,
                'vehicle_frame_wt': sheet_obj.cell(i, 5).value,
                'dcl_er_conc': dcl_er,
                'owner_system': owner_system,
                'rmk': sheet_obj.cell(i, 6).value,
                'state': 'wait_lg_approve',
                'vendor_id': self.env.user.vendor_id.id,
                'plant_id': plant_id,
                'create_uid': self._uid,
                'iac_write_uid': self._uid,
                'create_date': cw_date,
                'iac_write_date': cw_date,
                'org_code': org_code,
                'chg_tms_cnt':0
            }
            pass_port_header_object = self.env['iac.customs.pass.port.header'].create(pass_port_header_vals)
            # self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no)]).write({
            #     'pass_port_id':pass_port_header_object.id
            # })

            total_gross_wt = 0
            total_net_wt = 0
            total_wt = 0
            rlt_no = ''
            for hed_line in range(9, 9+rows):
                org_no = sheet_obj.cell(hed_line, 11).value.replace(' ', '')
                # self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no)]).write({
                #     'pass_port_id':pass_port_header_object.id
                # })
                if sheet_obj.cell(hed_line, 10).value == sheet_obj.cell(hed, 0).value:
                    self.env['iac.customs.sas.header'].search([('sas_stock_no', '=', org_no)]).write({
                        'pass_port_id': pass_port_header_object.id
                    })
                    head_obj_gross_wt = self.env['iac.customs.sas.header'].search([('sas_stock_no','=',org_no)])
                    print type(head_obj_gross_wt.gross_wt),type(sheet_obj.cell(hed_line, 4).value)
                    total_gross_wt+=head_obj_gross_wt.gross_wt
                    total_net_wt += head_obj_gross_wt.net_wt
                    # if hed_line-9==rows-1:
                    #     rlt_no += org_no
                    # else:
                    rlt_no += org_no+'\\'
                    passp_bind_sas_vals = {
                            'pass_port_header_id': pass_port_header_object.id,
                            'rlt_tb_typecd': '2',
                            'sas_header_id': head_obj_gross_wt.id,
                            'create_uid': self._uid,
                            'iac_write_uid': self._uid,
                            'create_date': cw_date,
                            'iac_write_date': cw_date
                        }
                    action_history_obj = self.env['iac.customs.action.history'].create({
                        'customs_doc_type': 'pass_port',
                        'pass_port_id': pass_port_header_object.id,
                        'action': 'Vendor create pass port',
                        'iac_write_uid': self._uid,
                        'iac_write_date': cw_date
                    })
                    self.env['iac.customs.pass.port.bind.sas'].create(passp_bind_sas_vals)
            print rlt_no.rstrip('\\')
            print sheet_obj.cell(hed, 4).value,type(sheet_obj.cell(hed, 4).value)
            total_wt += total_gross_wt + sheet_obj.cell(hed, 4).value + sheet_obj.cell(hed, 5).value
            pass_port_header_vals.update({
                'total_gross_wt': total_gross_wt,
                'total_net_wt': total_net_wt,
                'total_wt': total_wt,
                'rlt_no': rlt_no.rstrip('\\')
            })
            pass_port_header_object.write(pass_port_header_vals)

            # except:
            #     self.env.cr.rollback()
            #     raise exceptions.ValidationError(u'创建核放单失败，请重新上传！')
            i+=1

        message = u'档案上传成功，%d张核放单建立成功，待IAC审核，请到核放单清单查看！'%(lrows,)
        return self.env['warning_box'].info(title="Message", message=message)

    @api.multi
    def action_download_check_file(self):
        file_dir = self.env["muk_dms.directory"].search([('name', '=', 'file_template')], limit=1, order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template = self.env["muk_dms.file"].search([('filename', '=', '厂商上传核放单模板_v1.1.xlsx')], limit=1,
                                                        order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!' % ("厂商上传核放单模板_v1.1.xlsx",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s' % (file_template.id,),
            'target': 'new',
        }
        return action









