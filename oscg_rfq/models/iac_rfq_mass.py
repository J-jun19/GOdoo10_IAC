# -*- coding: utf-8 -*-

import json
import xlwt
import time,base64
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
import odoo
import threading
import traceback
import math
_logger = logging.getLogger(__name__)

"""
对调用的任务进行包装,初始化odoo的env环境
"""
def odoo_env(func):
    def __decorator(self):    #add parameter receive the user information
        db_name = self.env.registry.db_name
        db = odoo.sql_db.db_connect(db_name)
        threading.current_thread().dbname = db_name
        cr = db.cursor()
        with api.Environment.manage():
            try:
                env=api.Environment(cr, self.env.uid, {})
                self.env=env
                func(self)

            except:
                traceback.print_exc()
        cr.commit()
        cr.close()

    return __decorator


class IacRfqMassBuyerWizard(models.TransientModel):
    """ BUYER 查询job生成的RFQ信息
    """
    _name = 'iac.rfq.mass.buyer.wizard'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    vendor_id=fields.Many2one('iac.vendor',string="Vendor")
    part_id=fields.Many2one('material.master',string="Part")

    division_id = fields.Many2one('division.code', string='Division Info')
    flag = fields.Selection([
                                 ('C', 'Init State'),
                                 ('Y', 'Need To Create RFQ'),
                                 ('N', 'Need Not To Create RFQ'),
                            ], string='Flag', default='C',)
    @api.multi
    def action_confirm(self):
        """
        筛选已经生成的rfq mass 数据
        :return:
        """
        domain=[('state','in',['draft','processing'])]
        for wizard in self:
            if wizard.plant_id.id != False:
                domain=domain+[('plant_id','=',wizard.plant_id.id),]

            if wizard.vendor_id.id != False:
                domain=domain+[('vendor_id','=',wizard.vendor_id.id),]

            if wizard.part_id.id!=False:
                domain=domain+[('part_id','=',wizard.part_id.id),]

            if wizard.division_id.id!=False:
                domain=domain+[('division_id','=',wizard.division_id.id),]
            if wizard.flag!=False:
                domain=domain+[('flag','=',wizard.flag),]
        #查询条件组合完成后,获取符合条件的记录
        rfq_mass_line_list=self.env['iac.rfq.mass.line'].search(domain)
        result_ids=[]
        if len(rfq_mass_line_list.ids)==0:
            raise UserError('No Record found !')

        result_ids=[g.id for g in rfq_mass_line_list]
        header_vals={
            'memo':domain
        }
        #rfq_mass_header=self.env['iac.rfq.mass.header'].create(header_vals)
        #rfq_line_ids=[]
        #rfq_line_ids_vals = {'rfq_line_ids': [(4, g.id) for g in rfq_mass_line_list]}
        #rfq_mass_header.write(rfq_line_ids_vals)
        result_ids=[5,6,7]
        #数据准备完成后应该跳转到相应的视图
        action = self.env.ref('oscg_rfq.action_iac_rfq_mass_line_buyer_list')
        action_window= {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': 'tree',
            'view_mode': 'tree',
            'target':'inline',
            'res_model': action.res_model,
            'domain': [('id', 'in', result_ids)],
            }
        return action_window

class IacRfqMassCmWizard(models.TransientModel):
    """ CM 查询job生成的RFQ信息
    """
    _name = 'iac.rfq.mass.cm.wizard'

    plant_id = fields.Many2one('pur.org.data', string="Plant")
    part_id=fields.Many2one('material.master',string="Part")
    vendor_id=fields.Many2one('iac.vendor',string="Vendor")
    division_id = fields.Many2one('division.code', string='Division Info')
    flag = fields.Selection([
                                 ('C', 'Init State'),
                                 ('N', 'Need Not To Create RFQ'),
                            ], string='Flag', default='C',)
    @api.multi
    def action_confirm(self):
        """
        筛选已经生成的rfq mass 数据
        :return:
        """
        domain=[('state','in',['draft','processing'])]
        for wizard in self:
            if wizard.plant_id.id != False:
                domain=domain+[('plant_id','=',wizard.plant_id.id),]

            if wizard.vendor_id.id != False:
                domain=domain+[('vendor_id','=',wizard.vendor_id.id),]

            if wizard.part_id.id!=False:
                domain=domain+[('part_id','=',wizard.part_id.id),]

            if wizard.division_id.id!=False:
                domain=domain+[('division_id','=',wizard.division_id.id),]
            if wizard.flag!=False:
                domain=domain+[('flag','=',wizard.flag),]
        #查询条件组合完成后,获取符合条件的记录
        rfq_mass_line_list=self.env['iac.rfq.mass.line'].search(domain)
        if len(rfq_mass_line_list.ids)==0:
            raise UserError('No Record found !')

        header_vals={
            'memo':domain
        }
        rfq_mass_header=self.env['iac.rfq.mass.header'].create(header_vals)
        #rfq_line_ids=[]
        rfq_line_ids_vals = {'rfq_line_ids': [(4, g.id) for g in rfq_mass_line_list]}
        rfq_mass_header.write(rfq_line_ids_vals)

        #数据准备完成后应该跳转到相应的视图
        action = self.env.ref('oscg_rfq.action_iac_rfq_mass_header_cm_form')

        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': 'form',
            'target': action.target,
            'res_model': action.res_model,
            'res_id':rfq_mass_header.id
        }

class IacRfqMassVariant(models.Model):
    """对于久未异动的rfq的生成批量数据
    """
    _name = 'iac.rfq.mass.variant'
    plant_id = fields.Many2one('pur.org.data', 'Plant Info')
    key = fields.Char('Variant Name')
    value=fields.Char('Variant Value')
    memo = fields.Text('Memo')

class IacRfqMassJob(models.Model):
    """当前批量产生久未异动的job信息
    """
    _name = 'iac.rfq.mass.job'
    start_time=fields.Datetime(string='Start Time Of Job')
    end_time=fields.Datetime(string='End Time Of Job')
    proc_part_count=fields.Integer(string='Process Part Count')
    idle_part_count=fields.Integer(string='Idle Part Count')
    total_part_count=fields.Integer(string='Total Part Count')
    fail_part_count=fields.Integer(string='Total Part Count')
    state=fields.Selection([('processing','Processing'),('done','DONE')],string='Status',default='processing')
    job_ex_line_ids=fields.One2many('iac.rfq.mass.job.ex','job_id',string='Job Process Exception List')
    memo = fields.Text('Memo')

    def proc_get_page_list(self, record_count, limit_count):
        page_list = []
        if record_count <= limit_count:
            page_list.append(0)
            return page_list

        #计算分页偏移量
        offset_count = 0
        while offset_count <= record_count:
            page_list.append(offset_count)
            offset_count = offset_count + limit_count
        return page_list;


    @odoo_env
    @api.model
    def job_gen_rfq_mass(self):
        #设定默认记录分页记录数量
        limit_count = 1000
        #分页数组，存储sql 语句中的offset 参数
        page_list = []
        table_name="material_master"
        select_count = "select count(*) from %s" % (table_name,)
        self.env.cr.execute(select_count)
        record_count_result = self.env.cr.fetchall()

        record_count = record_count_result[0][0]


        #获取目标表的总记录数量
        page_list = self.proc_get_page_list(record_count, limit_count)

        #便利分页数组调用数据库中的存储过程完成任务
        insert_count_sum = 0
        update_count_sum = 0
        fail_count_sum = 0
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        job_vals={
            "start_time":start_time,
        }
        cur_job=self.env["iac.rfq.mass.job"].create(job_vals)
        db_func_name='proc_get_rfq_idle_mass'
        idle_count_sum=0
        fail_count_sum=0
        v_update_count_sum=0
        last_his_id=0
        for offset_count in page_list:
            sql_text="select * from " + db_func_name + "(%s,%s,%s) as " % (cur_job.id,limit_count, last_his_id)
            _logger.debug(sql_text)
            #self.env.cr.execute("select * from " + db_func_name + "(%s,%s,%s)",
            #           (cur_job.id,limit_count, offset_count))
            self.env.cr.execute("SELECT                                    " \
                                "	*                                      " \
                                "FROM                                      " \
                                "	public.proc_get_rfq_idle_mass (    " \
                                "		%s,                                " \
                                "		%s,                                 " \
                                "		%s                               " \
                                "	) AS (                                 " \
                                "		v_last_part_id int4,               " \
                                "		v_idle_count int4,                 " \
                                "		v_fail_count int4,                 " \
                                "		v_update_count int4                " \
                                "	)                                      ",(cur_job.id,last_his_id,limit_count))
            for v_last_part_id,v_idle_count, v_fail_count,v_update_count in self.env.cr.fetchall():
                idle_count_sum = idle_count_sum + v_idle_count
                fail_count_sum = fail_count_sum + v_fail_count
                _logger.debug("executing db func %s ,insert records:%s,fail records:%s" % (
                db_func_name, v_idle_count, v_fail_count))
                last_his_id=v_last_part_id
            self.env.cr.commit()
        _logger.debug("execute db func %s completed,total inserted records:%s,total failed records:%s " \
                      ",total process records:%s,last process id is %s" % (
        db_func_name, idle_count_sum, fail_count_sum,v_update_count_sum,last_his_id))
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        job_vals={
            "end_time":end_time,
            "idle_part_count":idle_count_sum,
            "fail_part_count":fail_count_sum,
            "state":"done",
        }

        cur_job.write(job_vals)
        self.env.cr.commit()


class IacRfqMassJobEx(models.Model):
    """当前批量产生久未异动的job处理后
       的异常信息列表
    """
    _name = 'iac.rfq.mass.job.ex'
    job_id=fields.Many2one('iac.rfq.mass.job',string='Job Info')
    part_id=fields.Many2one('material.master',string='Part Info')
    part_code=fields.Char(string='Part No')
    plant_id=fields.Many2one('pur.org.data',string='Plant Info')
    plant_code=fields.Char(string='Plant Code')
    ex_msg = fields.Text('Exception Message')
    last_rfq_his_id=fields.Many2one('inforecord.history','Rfq History Info')

class IacRfqMassHeader(models.Model):
    """当前的模型作用是对job生成的rfq进行分组
        让buyer和cm能够各自批量处理rfq
        buyer和cm查询多条rfq后，通过多对多关联管理rfq数据
    """
    _name = 'iac.rfq.mass.header'
    memo = fields.Text('Memo')
    rfq_line_ids = fields.Many2many(
        'iac.rfq.mass.line',
        'iac_rfq_mass_header_rfq_mass_line',
        'rfq_mass_header_id', 'rfq_mass_line_id',
        string=u"Rfq Mass Line Group Info")

class IacRfqMassLine(models.Model):
    """对于久未异动的rfq的生成批量数据
    """
    _name = 'iac.rfq.mass.line'
    note = fields.Text('Memo')
    reason_id = fields.Many2one('iac.rfq.mass.line.reason',string="Reason Code")
    other_reason=fields.Char(string="Other Reason")
    job_id=fields.Many2one('iac.rfq.mass.job',string='Job Info')
    expected_price = fields.Float(string="Expected Price",digits=(18,6))
    expected_valid_from = fields.Date(string='Expected Valid From')
    expected_valid_to = fields.Date(string='Expected Valid To')
    last_sum_amount=fields.Monetary(string='Amount In Last 3 Months')
    last_rfq_his_id=fields.Many2one('inforecord.history','Rfq History Info')

    input_price = fields.Float(string="Price",digits=(18,6))
    rfq_price = fields.Float(string="Price")
    valid_from = fields.Date('Valid From')
    valid_to = fields.Date('Valid To')
    moq = fields.Float(string="MOQ")
    mpq = fields.Float(string="MPQ")
    lt = fields.Integer(string="LTIME")
    cw = fields.Selection(string="CW",selection='_selection_cw')
    rw = fields.Selection(string="RW",selection='_selection_rw')
    # six factor: moq/mpq/lt/cw/rw/tax
    tax = fields.Selection([
                            ('J0','J0 0% input tax, China'),
                            ('J1','J1 17% input tax, China'),
                            ('J2','J2 13% input tax, China'),
                            ('J3','J3 6% input tax, China'),
                            ('J4','J4 4% input tax, China'),
                            ('J5','J5 7% input tax, China'),
                            ('J6','J6 3% input tax, China'),
                            ('J7','J7 11% input tax, China'),
                            ('J8','J8 5% input tax, China'),
                            ('J9','J9 16% input tax, China'),
                            ('JA','JA 10% input tax, China'),
                            ('11','11 5% Expense/Material -Deductible'),
                            ('V0','V0 No Tax Transaction Or Foreign Purchase '),
                               ],string="Tax")

    price_unit = fields.Float('Price unit')
    vendor_id = fields.Many2one('iac.vendor', string='Vendor Name',domain=[('state','=','done'),('vendor_type','in',['normal','spot'])])
    vendor_code = fields.Char(related='vendor_id.vendor_code',string="Vendor Code")
    part_id = fields.Many2one('material.master',string='Part No#',compute='_compute_fields',store=True)
    part_description = fields.Char(related='part_id.part_description')
    part_code = fields.Char('Part NO.')
    plant_id = fields.Many2one('pur.org.data',string='Plant Code')
    division_id = fields.Many2one('division.code',string='Divsion',readonly=True)
    buyer_code_id = fields.Many2one('buyer.code',string='Buyer Code Info')
    buyer_code=fields.Char(string='Buyer Code From SAP')
    purchase_org_id = fields.Many2one('vendor.plant','Purchase Orgnization')
    text = fields.Text('Text')
    currency_id = fields.Many2one('res.currency', string='Currency')
    flag = fields.Selection([
                                 ('C', 'Init State'), #quote
                                 ('Y', 'New RFQ'),
                                 ('N', ' No Cost Down'),
                                 ], string='Status', default='C',)
    state = fields.Selection([
                                 ('draft', 'Draft'), #quote
                                 ('processing', 'Processing'),
                                 ('done', 'Done'),
                                 ('cancel', 'Cancel'),
                                 ], string='Process Status', default='draft',)
    sap_price = fields.Monetary('Current SAP Price')
    cost_up = fields.Boolean(string="Cost Up")
    low_by_all_site = fields.Boolean(string="Low Price By All Site")
    disapproval_comm = fields.Text(string="Disapproval Comments")

    manufacturer_part_no = fields.Char('Manufacturer Part No')
    release_flag = fields.Char('Release Flag')
    buyer_partner_id = fields.Many2one('res.partner','Buyer ERP ID')
    uom = fields.Integer('Uom')
    line_text = fields.Char(string="Line text")
    vendor_part_no = fields.Char('Vendor Part No')
    order_reason = fields.Char(string="order_reason")


    payment_term = fields.Char(string="Payment_term")
    incoterm = fields.Char(string="Incoterm")
    incoterm2 = fields.Char(string="Incoterm2")
    price_control = fields.Selection([('1','by PO date'),('2','by delivery date')],string="Price control")
    active = fields.Boolean(string="Active",default=True)

    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.user.company_id.id)

    supplier_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    country_code = fields.Char('Country Code')
    rfq_id=fields.Many2one('iac.rfq',string='RFQ Info')

    @api.multi
    def write(self,vals):
        #校验价格数据是否合法
        if "expected_price" in vals:
            if not self.validate_float_6(vals["expected_price"]):
                raise UserError(_("小数位数太多!不能超过6位!"))
        result=super(IacRfqMassLine,self).write(vals)
        self.validate_record()
        return result
    def validate_float_6(self,float_val):
        try_price=float_val*math.pow(10,6)
        digits_part=abs(round(try_price-round(try_price),2))
        if digits_part>0.01:
            #抛出异常,小数位太多
            #raise UserError(_("小数位数太多!不能超过6位!"))
            return False
        else:
            return True
    def validate_record(self):
        """
        记录保存后进行校验,校验数据是否合法,只能被单条记录进行调用
        :return:
        """
        if self.expected_valid_to<self.expected_valid_from and self.flag=='Y':
            raise UserError('Expected Valid From Date cant not greater thean Expected Valid To Date')
        if self.expected_price<=0 and self.flag=='Y':
            raise UserError('Expected Price must greater than zero')

        delta = relativedelta(fields.Date.from_string(self.expected_valid_to), fields.Date.from_string(self.expected_valid_from))
        if delta.years >= 2 and self.flag=='Y':
            raise ValidationError(_('Expected Valid to date -Expected Valid from date > 2 years!'))
    @api.multi
    def button_to_apply(self):
        """
        复制当前的RFQ MASS 记录到正式的RFQ表中
        :return:
        """
        relate_fields=['plant_id','vendor_id','currency_id',]
        spec_fields=['input_price','valid_from','valid_from',]
        fields = ['part_code','price_control','lt','moq','mpq','rw','cw','tax']

        for rfq_line in self:
            #排除N状态,不生成rfq
            if rfq_line.flag=='N':
               rfq_line.write({"state":"done"})
               continue

            #避免重复提交,done 状态的不处理
            if rfq_line.state=='done':
                continue

            rfq_vals_list=rfq_line.read(fields)
            rfq_vals=rfq_vals_list[0]
            rfq_vals["plant_id"]=rfq_line.plant_id.id
            rfq_vals["part_id"]=rfq_line.part_id.id
            rfq_vals["vendor_id"]=rfq_line.vendor_id.id
            rfq_vals["currency_id"]=rfq_line.currency_id.id

            rfq_vals["input_price"]=rfq_line.expected_price
            rfq_vals["valid_from"]=rfq_line.expected_valid_from
            rfq_vals["valid_to"]=rfq_line.expected_valid_to

            rfq_vals["price_unit"]=rfq_line.price_unit
            rfq_vals["division_id"]=rfq_line.division_id.id
            rfq_vals["buyer_code"]=rfq_line.buyer_code_id.id

            rfq_vals["state"]="rfq"
            rfq_vals["type"]="rfq"
            rfq_vals["new_type"]="job_create"
            rfq_id_rec=self.env['iac.rfq'].create(rfq_vals)
            #数据建议成功的情况下,更新当前的状态
            rfq_line.write({"rfq_id":rfq_id_rec.id,"state":"done"})

    #flag = fields.Selection([('c','C'),('n','N'),('y','Y')],string='Flag')
    @api.model
    def _selection_cw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id','=','Cancel window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

    @api.model
    def _selection_rw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id','=','Reschedule window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

class IacRfqMassHeaderBuyer(models.Model):
    """buyer专用的模型处理rfq分组
    """
    _name = 'iac.rfq.mass.header.buyer'
    _inherit="iac.rfq.mass.header"
    _table="iac_rfq_mass_header"
    rfq_line_ids = fields.Many2many(
        'iac.rfq.mass.line.buyer',
        'iac_rfq_mass_header_rfq_mass_line',
        'rfq_mass_header_id', 'rfq_mass_line_id',
        string=u"Rfq Mass Line Group Info")

    @api.multi
    def button_to_submit(self):
        """
        提交更改的数据到正式rfq表中
        :return:
        """
        for rfq_line in self.rfq_line_ids:
            if rfq_line.flag=='C':
                raise UserError("Some RFQ Line flag is ( Init State)")
            if rfq_line.flag=='Y':
                if rfq_line.expected_price==False:
                    raise UserError("Expected Price must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_from==False:
                    raise UserError("Expected Valid From must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to==False:
                    raise UserError("Expected Valid To must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to<rfq_line.expected_valid_from:
                    raise UserError("Expected Valid To is lower than Expected Valid From")
                rfq_line.button_to_apply()
            if rfq_line.flag=='N':
                if rfq_line.reason_id==False:
                    raise UserError("Reason Code must be specific when flag is (Need Not To Create RFQ)")
                if rfq_line.other_reason==False:
                    raise UserError("Other Reason must be specific when flag is (Need Not To Create RFQ)")
                rfq_line.button_to_apply()

        action = self.env.ref('oscg_rfq.action_iac_rfq_mm_release')
        action_window={
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode':"tree",
            'target': action.target,
            'res_model': action.res_model,
        }
        return action_window

class IacRfqMassLineBuyer(models.Model):
    """buyer专用的模型处理rfq条目
    """
    _name = 'iac.rfq.mass.line.buyer'
    _inherit="iac.rfq.mass.line"
    _table="iac_rfq_mass_line"
    @api.multi
    def set_state_C(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"C"})
        pass

    @api.multi
    def set_state_Y(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"Y"})
        pass

    @api.multi
    def set_state_N(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"N"})

    @api.multi
    def submit(self):

        for rfq_line in self:
            if rfq_line.flag=='C':
                raise UserError("Some RFQ Line flag is ( Init State)")
            if rfq_line.flag=='Y':
                if rfq_line.expected_price==False:
                    raise UserError("Expected Price must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_from==False:
                    raise UserError("Expected Valid From must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to==False:
                    raise UserError("Expected Valid To must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to<rfq_line.expected_valid_from:
                    raise UserError("Expected Valid To is lower than Expected Valid From")
                rfq_line.button_to_apply()
            if rfq_line.flag=='N':
                if not rfq_line.reason_id.exists():
                    raise UserError("Reason Code must be specific when flag is (Need Not To Create RFQ)")
                if rfq_line.other_reason==False:
                    raise UserError("Other Reason must be specific when flag is (Need Not To Create RFQ)")
                if rfq_line.other_reason==False:
                    raise UserError("Other Reason must be specific when flag is (Need Not To Create RFQ)")


                 #Price, Valid From, Valid To
                rfq_line.expected_price=False
                rfq_line.expected_valid_from=False
                rfq_line.expected_valid_to=False
                rfq_line.button_to_apply()

    @api.multi
    def write(self,vals):

        result=super(IacRfqMassLineBuyer,self).write(vals)
        return result

class IacRfqMassHeaderCm(models.Model):
    """Cm专用的模型处理rfq分组
    """
    _name = 'iac.rfq.mass.header.cm'
    _inherit="iac.rfq.mass.header"
    _table="iac_rfq_mass_header"
    rfq_line_ids = fields.Many2many(
        'iac.rfq.mass.line.cm',
        'iac_rfq_mass_header_rfq_mass_line',
        'rfq_mass_header_id', 'rfq_mass_line_id',
        string=u"Rfq Mass Line Group Info")

    @api.multi
    def button_to_submit(self):
        """
        提交更改的数据到正式rfq表中
        :return:
        """
        for rfq_line in self.rfq_line_ids:
            if rfq_line.flag=='C':
                raise UserError("Some RFQ Line flag is ( Init State)")
            if rfq_line.flag=='N':
                if rfq_line.reason_id==False:
                    raise UserError("Reason Code must be specific when flag is (Need Not To Create RFQ)")
                if rfq_line.other_reason==False:
                    raise UserError("Other Reason must be specific when flag is (Need Not To Create RFQ)")
                rfq_line.button_to_apply()

        action = self.env.ref('oscg_rfq.action_rfq_quote')
        action_window={
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode':"tree",
            'target': action.target,
            'res_model': action.res_model,
        }
        return action_window

class IacRfqMassLineCm(models.Model):
    """Cm专用的模型处理rfq条目
    """
    _name = 'iac.rfq.mass.line.cm'
    _inherit="iac.rfq.mass.line"
    _table="iac_rfq_mass_line"
    flag = fields.Selection([
                                 ('C', 'Init State'), #quote
                                 ('N', 'No Cost Down'),
                                 ], string='Status', default='C',)

    @api.multi
    def set_state_C(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"C"})
        pass

    @api.multi
    def set_state_Y(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"Y"})
        pass

    @api.multi
    def set_state_N(self):
        for rfq_mass_line in self:
            rfq_mass_line.write({"flag":"N"})

    @api.multi
    def submit(self):

        for rfq_line in self:
            if rfq_line.flag=='C':
                raise UserError("Some RFQ Line flag is ( Init State)")
            if rfq_line.flag=='Y':
                if rfq_line.expected_price==False:
                    raise UserError("Expected Price must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_from==False:
                    raise UserError("Expected Valid From must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to==False:
                    raise UserError("Expected Valid To must be specific when flag is (Need To Create RFQ)")
                if rfq_line.expected_valid_to<rfq_line.expected_valid_from:
                    raise UserError("Expected Valid To is lower than Expected Valid From")
                rfq_line.button_to_apply()
            if rfq_line.flag=='N':
                if not rfq_line.reason_id.exists():
                    raise UserError("Reason Code must be specific when flag is (Need Not To Create RFQ)")
                rfq_line.expected_price=False
                rfq_line.expected_valid_from=False
                rfq_line.expected_valid_to=False
                rfq_line.button_to_apply()


class IacRfqMassLineReason(models.Model):
    """
    为RFQ Mass Line设置原因字段
    """
    _name = 'iac.rfq.mass.line.reason'
    name = fields.Char('Reason')
    memo =fields.Text('Description')

    _sql_constraints = [('iac_rfq_mass_line_reason_unique', 'unique(name)', 'Reason Name Must Be Unique.')]
