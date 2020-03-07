# -*- coding: utf-8 -*-

import re
from odoo import models, fields, api, exceptions, _
import odoo
import threading
import logging
import traceback
import datetime
_logger = logging.getLogger(__name__)


def create_rfq_new_vs_old(self,rfq_obj,rfd_id_param,reason_flag):
    """
    CM,AS上传RFQ时产生相同料号且目前所有有效的rfq，
    可能会存在多行，
    有效单价为：done状态，valid from <= today and valid to >= today

    :param self:
    :param rfq_obj:
    :param rfd_id_param: string
    :return:
    """

    # 这里存在一个问题，如果当下有某个其他厂区相同料号的RFQ正在走流程，是不会记录到这张表的，
    # 但是未来它也签核完毕生效了，就会有人跑来说，新旧单价对应关系记录不完整，
    # 但是我们PM给的需求就是比对当下已经生效的，所以也没什么好办法。2019-12-04 ZPW

    # 找到当前料号在不同厂区下的part_id
    part_id_list = []
    bvi_vendor_account_group = []
    rfq_material_obj = self.env['material.master'].search([('id', '=', rfq_obj.part_id.id)])
    all_plant_part_objs = self.env['material.master'].sudo().search([('part_no', '=', rfq_material_obj.part_no)])
    for plant_part_obj in all_plant_part_objs:
        part_id_list.append(plant_part_obj.id)

    # 系统中所有bvi厂商
    bvi_vendor_objs = self.env['iac.vendor.account.group'].search([('vendor_type', '=', 'bvi')])
    for bvi_vendor in bvi_vendor_objs:
        bvi_vendor_account_group.append(bvi_vendor.account_group)

    # 查询到此笔rfq相同料号并且有效的所有旧rfq------('id','!=',rfq_obj.id),
    # ('valid_from', '<=', datetime.datetime.now().strftime("%Y-%m-%d")),
    # ('valid_to', '>=', datetime.datetime.now().strftime("%Y-%m-%d")),
    old_rfq_objs = self.env['iac.rfq'].search([('part_id','in',part_id_list),
                                               ('state','=','sap_ok')])
    rfq_up_list = []
    rfq_web_num_list = []
    ori_plants_rfq_objs = []
    webnum_trans_lambda = lambda r: int(r[3:]) if r not in (False, '', None) else 0
    # 排除bvi厂商的rfq
    for rfq in old_rfq_objs:
        active_flag = 0
        for ori_plant_vendor_rfq in ori_plants_rfq_objs:
            if rfq.sudo().vendor_id.vendor_account_group not in bvi_vendor_account_group and rfq.plant_id.id==ori_plant_vendor_rfq[0] and rfq.vendor_id.id==ori_plant_vendor_rfq[1]:
                ori_plant_vendor_rfq[2].append(rfq)
                if webnum_trans_lambda(rfq.webflow_number) not in ori_plant_vendor_rfq[3]:
                    ori_plant_vendor_rfq[3].append(webnum_trans_lambda(rfq.webflow_number))
                active_flag += 1
        if rfq.sudo().vendor_id.vendor_account_group not in bvi_vendor_account_group and active_flag == 0:
            ori_plants_rfq_objs.append([rfq.plant_id.id,rfq.vendor_id.id,[rfq],[webnum_trans_lambda(rfq.webflow_number)]])

    if ori_plants_rfq_objs:
        i = 0
        try:
            for plant,vendor,old_rfq_objes,web_num in ori_plants_rfq_objs:
                x = 1
                for old_rfq_obj in old_rfq_objes:
                    valus = {}
                    # 1.如果币别相同，直接比较单价大小，得出up/down/nochange
                    # 2.计算变动幅度
                    if old_rfq_obj.currency_id.id == rfq_obj.currency_id.id:
                        # 涨价
                        if rfq_obj.input_price > old_rfq_obj.input_price:
                            ratio = (rfq_obj.input_price-old_rfq_obj.input_price)/old_rfq_obj.input_price
                            valus.update({'price_compare': 'up',
                                          'ratio': ratio,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})
                            # i += 1
                            # rfq_up_list.append(i)

                        # 降价
                        elif rfq_obj.input_price < old_rfq_obj.input_price:
                            ratio = (rfq_obj.input_price - old_rfq_obj.input_price) / old_rfq_obj.input_price
                            valus.update({'price_compare': 'down',
                                          'ratio': ratio,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})
                        # 不变
                        else:
                            valus.update({'price_compare': 'nochange',
                                          'ratio': 0,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})
                        # 如果此笔旧rfq是这组中最新的一笔，就给这笔对照资料打上new_flag标记
                        if max(web_num)!=0 and webnum_trans_lambda(old_rfq_obj.webflow_number) == max(web_num) and old_rfq_obj.valid_from <= datetime.datetime.now().strftime("%Y-%m-%d") and old_rfq_obj.valid_to >= datetime.datetime.now().strftime("%Y-%m-%d"):
                            valus.update({'new_flag':'Y'})
                            if valus.get('price_compare') == 'up':
                                i += 1
                                rfq_up_list.append(i)
                        # 如果这组rfq中都没有webflow_nub，就取id最大那一笔打个标记，但是当作不涨价
                        elif max(web_num) == 0 and x == len(old_rfq_objes):
                            id_list = []
                            for ol_rfq in old_rfq_objs:
                                id_list.append(ol_rfq.id)
                            for o_rfq in old_rfq_objes:
                                if o_rfq.id == max(id_list):
                                    valus.update({'new_flag': 'Y'})
                                    if valus.get('price_compare') == 'up':
                                        i += 1
                                        rfq_up_list.append(i)
                        x += 1
                        new_vs_olds = self.env['iac.rfq.new.vs.old'].create(valus)

                    # 1.如果币别不同，新旧单价全部转换成美金，得出up/down/nochange
                    # 2.计算变动幅度
                    else:
                        new_rfq_usd = (self.env['iac.currency.exchange'].search(
                            [('from_currency_id', '=', rfq_obj.currency_id.id),
                             ('state','=','active')]).to_currency_amount / 1000)*rfq_obj.input_price
                        old_rfq_usd = (self.env['iac.currency.exchange'].search(
                            [('from_currency_id', '=', old_rfq_obj.currency_id.id),
                             ('state', '=', 'active')]).to_currency_amount / 1000)*old_rfq_obj.input_price

                        # 涨价
                        if new_rfq_usd > old_rfq_usd:
                            ratio = (new_rfq_usd-old_rfq_usd)/old_rfq_usd
                            valus.update({'price_compare': 'up',
                                          'ratio': ratio,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})
                            # i += 1
                            # rfq_up_list.append(i)

                        # 降价
                        elif new_rfq_usd < old_rfq_usd:
                            ratio = (new_rfq_usd - old_rfq_usd) / old_rfq_usd
                            valus.update({'price_compare': 'down',
                                          'ratio': ratio,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})

                        # 不变
                        else:
                            valus.update({'price_compare': 'nochange',
                                          'ratio': 0,
                                          rfd_id_param: rfq_obj.id,
                                          'old_rfq_id': old_rfq_obj.id})
                        # 如果此笔旧rfq是这组中最新的一笔，就给这笔对照资料打上new_flag标记
                        if max(web_num)!=0 and webnum_trans_lambda(old_rfq_obj.webflow_number) == max(web_num) and old_rfq_obj.valid_from <= datetime.datetime.now().strftime("%Y-%m-%d") and old_rfq_obj.valid_to >= datetime.datetime.now().strftime("%Y-%m-%d"):
                            valus.update({'new_flag': 'Y'})
                            if valus.get('price_compare') == 'up':
                                i += 1
                                rfq_up_list.append(i)
                        # 如果这组rfq中都没有webflow_nub，就取id最大那一笔打个标记，但是当作不涨价
                        elif max(web_num) == 0 and x == len(old_rfq_objes):
                            id_list = []
                            for ol_rfq in old_rfq_objs:
                                id_list.append(ol_rfq.id)
                            for o_rfq in old_rfq_objes:
                                if o_rfq.id == max(id_list):
                                    valus.update({'new_flag': 'Y'})
                                    if valus.get('price_compare') == 'up':
                                        i += 1
                                        rfq_up_list.append(i)
                        x += 1
                        new_vs_olds = self.env['iac.rfq.new.vs.old'].create(valus)

                    # 1.如果传进来的rfd_id_param != 'current_rfq_id'
                    # 2.如果角色是MM继续执行下面的代码，写上current_rfq_id
                    if rfd_id_param != 'current_rfq_id':
                        for item in self.env.user.groups_id:
                            if item.name == 'Buyer':
                                new_vs_olds.write({'current_rfq_id': rfq_obj.rfq_id.id})
            # 判断角色是as并且如果是涨价的rfq,但是上传涨价原因标志为False,就将状态改成reason
            if i > 0 and not reason_flag:
                for item in self.env.user.groups_id:
                    if item.name == 'AS':
                        rfq_obj.write({'state': 'reason'})

        except:
            self.env.cr.rollback()
            raise exceptions.ValidationError(traceback.format_exc())

    if len(rfq_up_list)>0:
        return True
    else:
        return False


def validate_costup_reason(self,rfq_obj,state):
    """
    校验RFQ涨价原因
    :param self:
    :param rfq_obj:
    :return:
    """

    if state == 'reason' and not rfq_obj.costup_reason_id:
        raise exceptions.ValidationError(u'状态为(%s)plant_code为(%s)vendor_code为(%s)part_no为(%s)有存在其他较低价格，请选择价格不同的原因!'
                                         % (rfq_obj.state, rfq_obj.plant_id.plant_code, rfq_obj.vendor_id.vendor_code,
                                            rfq_obj.part_id.part_no))

    elif state == 'reason':
        try:
            rfq_obj.write({'state': 'as_uploaded'})
        except:
            self.env.cr.rollback()
            raise exceptions.ValidationError(traceback.format_exc())

    elif state in ['replay','draft']:
        up_rfq_obj = self.env['iac.rfq.new.vs.old'].search([('current_rfq_id','=',rfq_obj.id),
                                               ('price_compare','=','up')],limit=1)
        if not up_rfq_obj and rfq_obj.cost_up_reason_id:
            raise exceptions.ValidationError(u'状态为(%s)plant_code为(%s)vendor_code为(%s)part_no为(%s)不存在其他较低价格，不需要填写价格不同的原因！'
                                             %(rfq_obj.state,rfq_obj.plant_id.plant_code,rfq_obj.vendor_id.vendor_code,rfq_obj.part_id.part_no))
        elif up_rfq_obj and not rfq_obj.cost_up_reason_id:
            raise exceptions.ValidationError(u'状态为(%s)plant_code为(%s)vendor_code为(%s)part_no为(%s)有存在其他较低价格，必须填写价格不同的原因！'
                                             % (rfq_obj.state, rfq_obj.plant_id.plant_code, rfq_obj.vendor_id.vendor_code,rfq_obj.part_id.part_no))


def parse_costup_reason_true(self,item_no):
    """
    对于直接在excel里面填写了涨价原因的资料要校验涨价原因是否存在
    :param self:
    :param item_no:
    :return:
    """
    reason_obj = self.env['iac.rfq.cost.up.reason'].search([('item_no','=',item_no),
                                               ('active','=',True)])
    if not reason_obj:
        process_msg = u'表格资料里vendor(%s)part_no(%s)的价格不同的原因填写错误,请检查'
        process_result = False
        return process_msg,process_result

    else:
        process_msg = ''
        process_result = True
        return process_msg,process_result


def download_error_excel(self,ex_message_list):
    """
    上传错误信息时，跳转下载错误提示链接到excel
    :param self:
    :param rfq_obj:
    :return:
    """
    action_url = self.env['iac.file.import'].get_action_url(self.file, ex_message_list)
    return False,action_url





