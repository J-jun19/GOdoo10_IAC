# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
import  traceback
import threading



class ASNJITRule(models.Model):
    _inherit = "asn.jitrule"

    '''
    外部系统只送E005 和E0062个白名单,对应 rule_type=1,rule_type=2
    VENDOR + BUYER - E005 rule_type 1
    VENDOR + PART - E006  rule_type 2
    rule_type:1 = vendor+buyer ,2 = vendor + part
    '''


    plant_code   =fields.Char("Plant Code")
    buyer_erp_id =fields.Char("Buyer Erp Id")
    vendor_code  =fields.Char("Vendor Code")
    pulling_type =fields.Char("Pulling Type")
    part_no      =fields.Char("Part No")
    part_no_4    =fields.Char("Part No First 4 Char")
    rule_type=fields.Selection([('1','1'),('2','2')],string="Rule Type")
    vendor_id = fields.Many2one('iac.vendor',string="Vendor",track_visibility='always')
    plant_id = fields.Many2one('pur.org.data', 'Plant',track_visibility='always')
    part_id = fields.Many2one('material.master.asn', 'Part No',track_visibility='always',compute = '_compute_fields',store=True)
    part_id_2 = fields.Many2one('material.master.asn', 'Part Info')
    buyer_code = fields.Many2one('buyer.code','Buyer Code',track_visibility='always')
    black_white_list = fields.Selection([
                                            ('I001','I001 INCLUDE BY MATERIAL'),
                                            ('E001','E001 EXCLUDE BY VENDOR'),
                                            ('E002','E002 EXCLUDE BY VENDOR + MATERIAL'),
                                            ('E003','E003 EXCLUDE BY MATERIAL'),
                                            ('E004','E004 EXCLUDE BY MATERIAL FIRST 4 CHAR'),
                                            ('E005','E005 EXCLUDE BY FP VENDOR + PURCHASE GROUP'),
                                            ('E006','E006 EXCLUDE BY FP VENDOR + MATERIAL'),
                                            ],string='Rule Category')
    vendor_id=fields.Many2one('iac.vendor.asn',string='Vendor Info')
    file_line_no=fields.Integer(string='File Line No')
    sequence=fields.Integer(string='Sequence Num')
    # black_white_list = fields.Selection([
    #    ('1','INCLUE BUY MATERIAL'),
    #    ('2','EXCLUDE BY FP VENDOR + PURCHASE GROUP'), #buyer code
    #    ('3','EXCLUDE BY FP VENDOR + MATERIAL'),
    #    ('4','EXCLUDE BY FP VENDOR'),
    #    ('5','EXCLUDE BY VENDOR + MATERIAL'),
    #    ('6','EXCLUDE BY MATERIAL'),
    #    ('7','EXCLUDE BY MATERIAL FIRST 4 CHAR'),
    #    ],string='Black or White List')
    validate_from = fields.Date('Valid From')
    validate_to = fields.Date('Valid To')
    state=fields.Selection([
                               ('cancel','Cancel'),
                               ('done','Done'),
                               ],string='Rule Status',default='done')

    @api.multi
    @api.depends('part_no', 'plant_id')
    def _compute_fields(self):
        for r in self:
            part = self.env['material.master.asn'].search(
                [('plant_id', '=', r.plant_id and r.plant_id.id or False), ('part_no', '=', r.part_no)])
            r.part_id = part and part[0].id or False
            if r.part_no and not r.part_id:
                raise UserError('Part Code is not exist!')


    @api.model
    def kakong(self,vendor_id,buyer_code,part_id,vendor_code,part_no,plant_id):
        '''
            黑名单规则优先,也就是说只要黑名单不存在就不卡控

            如果黑名单存在，白名单也存在，就不卡控
            如果黑名单存在，白名单不存在，就需要卡控
            返回值有3个
            1   布尔型，是否进行卡控
            2   数值型,当前最大可交量
            3   最大可交量记录id
        '''

        #bvi厂商不卡控最大可交量
        bvi_vendor = self.env['iac.vendor'].browse(vendor_id)
        if bvi_vendor.vendor_type == 'bvi':
            return False, 0, 0
        #191105 ning add   part_type是ZROH的要卡控可交量
        part_no_obj = self.env['material.master'].sudo().browse(part_id)
        if part_no_obj.part_type != 'ZROH':
            return False, 0, 0

        day = fields.Date.today()
        #公共部分条件
        date_domain=[('validate_from','<=',day),('validate_to','>=',day),('state','=','done')]

        #黑名单存在的情况下,是否卡控要看白名单是否存在
        domain = [('part_no', '=', part_no),('black_white_list','=','I001'),('plant_id','=',plant_id)]+date_domain
        rule_result=self.search(domain)
        if not rule_result.exists():
            #黑名单不存在的情况下,继续检查白名单
            domain_01 = date_domain + [('black_white_list','=','E001'),('vendor_id','=',vendor_id)]
            domain_02 = date_domain + [('black_white_list','=','E002'),('vendor_id','=',vendor_id),('part_no','=',part_no)]
            domain_03 = date_domain + [('black_white_list','=','E003'),('part_no','=',part_no),('plant_id','=',plant_id)]
            domain_04 = date_domain + [('black_white_list','=','E004'),('part_no_4','=',part_no[:4]),('plant_id','=',plant_id)]
            domain_05 = date_domain + [('black_white_list','=','E005'),('vendor_id','=',vendor_id),('buyer_code','=',buyer_code)]
            domain_06 = date_domain + [('black_white_list','=','E006'),('vendor_id','=',vendor_id),('part_no','=',part_no)]

            #如果白名单存在,那么不卡控
            white_result=self.search(domain_01)
            if  white_result.exists():
                return False,0,0

            white_result=self.search(domain_02)
            if  white_result.exists():
                return False,0,0

            white_result=self.search(domain_03)
            if  white_result.exists():
                return False,0,0

            white_result=self.search(domain_04)
            if  white_result.exists():
                return False,0,0

            white_result=self.search(domain_05)
            if  white_result.exists():
                return False,0,0

            white_result=self.search(domain_06)
            if  white_result.exists():
                return False,0,0

            #前面6种白名单都不存在的情况下,那么需要进行卡控,返回最大可交量信息
            return self.env['asn.maxqty'].max_kakong(vendor_id,part_id,vendor_code,part_no)
        else:
            #黑名单存在的情况下,卡控最大可交量
            return self.env['asn.maxqty'].max_kakong(vendor_id,part_id,vendor_code,part_no)





class IacASNJITRule(models.Model):
    _inherit = "asn.jitrule"
    _name="iac.asn.jitrule"
    _table="asn_jitrule"

    #校验记录是否合法,在create 或者write 之后调用
    def _validate_record(self):
        if self.black_white_list in ['E005','E006']:
            raise UserError("EXCLUDE BY FP VENDOR + MATERIAL , EXCLUDE BY FP VENDOR + PURCHASE GROUP can not maintain  in odoo")
        if self.black_white_list=='I001':
            if self.validate_from==False:
                raise UserError('Valid From can not be null')
            if self.validate_to==False:
                raise UserError('valid To can not be null')
            if not self.part_id.exists():
                raise UserError('Part Info can not be null')
            if not self.plant_id.exists():
                raise UserError('Plant Info can not be null')
            if self.validate_from>self.validate_to:
                raise UserError('Valid From  can not greater than Valid To')
            if self.part_id.plant_id.id!=self.plant_id.id:
                raise UserError('Part Plant Info is not same with Plant Info')
        if self.black_white_list=='E001':
            if self.validate_from==False:
                raise UserError('Valid From can not be null')
            if self.validate_to==False:
                raise UserError('Valid To can not be null')
            if not self.vendor_id.exists():
                raise UserError('Vendor Info can not be null')
            if not self.plant_id.exists():
                raise UserError('Plant Info can not be null')
            if self.validate_from>self.validate_to:
                raise UserError('Valid From  can not greater than Valid To')
            if self.vendor_id.plant.id!=self.plant_id.id:
                raise UserError('Vendor Plant Info is not same with Plant Info')
        if self.black_white_list=='E002':
            if self.validate_from==False:
                raise UserError('Valid From can not be null')
            if self.validate_to==False:
                raise UserError('Valid To can not be null')
            if not self.part_id.exists():
                raise UserError('Part Info can not be null')
            if not self.vendor_id.exists():
                raise UserError('Vendor Info can not be null')
            if not self.plant_id.exists():
                raise UserError('Plant Info can not be null')
            if self.validate_from>self.validate_to:
                raise UserError('Valid From  can not greater than Valid To')
            if self.vendor_id.plant.id!=self.plant_id.id:
                raise UserError('Vendor Plant Info is not same with Plant Info')
            if self.part_id.plant_id.id!=self.plant_id.id:
                raise UserError('Part Plant Info is not same with Plant Info')
        if self.black_white_list=='E003':
            if self.validate_from==False:
                raise UserError('Valid From can not be null')
            if self.validate_to==False:
                raise UserError('Valid To can not be null')
            if not self.part_id.exists():
                raise UserError('Part Info can not be null')
            if not self.plant_id.exists():
                raise UserError('Plant Info can not be null')
            if self.validate_from>self.validate_to:
                raise UserError('Valid From  can not greater than Valid To')
            if self.part_id.plant_id.id!=self.plant_id.id:
                raise UserError('Part Plant Info is not same with Plant Info')

        if self.black_white_list=='E004':
            if self.validate_from==False:
                raise UserError('Valid From can not be null')
            if self.validate_to==False:
                raise UserError('Valid To can not be null')
            if  self.part_no_4==False:
                raise UserError('Part No First 4 Char can not be null')
            if not len(self.part_no_4)==4:
                raise UserError('Part No First 4 Char length is not equal 4')
            if not self.plant_id.exists():
                raise UserError('Plant Info can not be null')
            if self.validate_from>self.validate_to:
                raise UserError('Valid From  can not greater than Valid To')

    def _find_last_rec(self):
        """
        寻找到当前记录之前的有效记录
        :return:
        """
        if self.black_white_list=='I001':
            domain=[('black_white_list','=','I001')]
            domain+=[('part_id_2','=',self.part_id_2.id)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E001':
            domain=[('black_white_list','=','E001')]
            domain+=[('vendor_id','=',self.vendor_id.id)]
            domain+=[('buyer_code','=',self.buyer_code.id)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E002':
            domain=[('black_white_list','=','E002')]
            domain+=[('vendor_id','=',self.vendor_id.id)]
            domain+=[('part_id_2','=',self.part_id_2.id)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E003':
            domain=[('black_white_list','=','E003')]
            domain+=[('vendor_id','=',self.vendor_id.id)]
            domain+=[('id','<',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E004':
            domain=[('black_white_list','=','E004')]
            domain+=[('part_no_4','=',self.part_no_4)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E005':
            domain=[('black_white_list','=','E005')]
            domain+=[('vendor_id','=',self.vendor_id.id)]
            domain+=[('buyer_code','=',self.buyer_code.id)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

        if self.black_white_list=='E006':
            domain=[('black_white_list','=','E006')]
            domain+=[('vendor_id','=',self.vendor_id.id)]
            domain+=[('part_id_2','=',self.part_id_2.id)]
            domain+=[('state','=','done')]
            domain+=[('id','<>',self.id)]
            last_rec=self.env["asn.jitrule"].search(domain,order='sequence desc',limit=1)
            return last_rec

    def _write_his_state(self):
        """
        根据当前记录,查找上一条记录,并且把上一条记录的状态标记为cancel
        :return:
        """
        last_rec=self._find_last_rec()
        if last_rec.exists():
            super(ASNJITRule,last_rec).write({"state":"cancel"})
            super(ASNJITRule,self).write({"sequence":last_rec.sequence+1})
        else:
            super(ASNJITRule,self).write({"sequence":1})


        #补充part_no vendor_code plant_code buyer_erp_id 字段
        update_vals={}
        if self.part_id_2.exists():
            update_vals["part_no"]=self.part_id_2.part_no
        if self.vendor_id.exists():
            update_vals["vendor_code"]=self.vendor_id.vendor_code
        if self.plant_id.exists():
            update_vals["plant_code"]=self.plant_id.plant_code
        if self.buyer_code.exists():
            update_vals["buyer_erp_id"]=self.buyer_code.buyer_erp_id
        super(ASNJITRule,self).write(update_vals)

    @api.model
    def create(self,vals):
        if "part_id_2" in vals:
            part_rec=self.env["material.master.asn"].browse(vals["part_id_2"])
            vals["part_no"]=part_rec.part_no
        result=super(ASNJITRule,self).create(vals)
        if result.part_id.exists():
            super(IacASNJITRule,result).write({"part_id_2":result.part_id.id})
        result._validate_record()
        result._write_his_state()
        return result

    @api.multi
    def write(self,vals):
        """
        变write为create
        :param vals:
        :return:
        """
        result=None
        for asn_rule in self:
            update_vals={
                "sequence":asn_rule.sequence,
                "state":"cancel"
            }
            copy_vals = self.copy_data(update_vals)[0]
            asn_rule_copy=self.env["asn.jitrule"].create(copy_vals)
            vals["sequence"]=asn_rule.sequence+1
            result=super(ASNJITRule,asn_rule).write(vals)
            asn_rule._validate_record()
        return result



class AsnJitruleImportWizard(models.TransientModel):
    _name = 'asn.jitrule.import.wizard'
    _inherit = 'iac.file.import'


    @api.multi
    def action_upload_file(self):
        """
        上传文件按钮入口
        :return:
        """
        model_name="iac.asn.jitrule"

        fields=['id','vendor_id','plant_id','part_no','part_no_4','buyer_code','black_white_list','validate_from','validate_to']
        process_result,import_result,action_url=super(AsnJitruleImportWizard,self).import_file(model_name,fields)
        if process_result==False:
            return action_url

        #导入成功的情况下,转入数据到正式表中
        file_vals = {
            'name': 'import-error-messages',
            'datas_fname': 'import-error-messages.xls',
            'description': 'rfq import error messages',
            'type': 'binary',
            'db_datas': self.file,
            }
        file_rec = self.env['ir.attachment'].create(file_vals)
        import_vals={
            'state': 'mm_updated',
            'mm_file_id':file_rec.id,
            }
        ids=import_result["ids"]
        return self.env['warning_box'].info(title=u"提示信息", message=u"导入数据操作成功！")
        #这里的res_model是由action 的context 传入,代表目标表模型
        #self.env[self.res_model].browse(ids).write(import_vals)
        #for rfq_line in self.env[self.res_model].browse(ids):
        #    rfq_line.apply_mm_update()


    def validate_parsed_data(self,data,import_fields):
        """
        校验刚刚通过解析的数据,子类可以重写当前函数,实现自定义的解析
        返回值有2个
        1   第一个表示校验是否成功
        2   错误信息列表
        :return:
        """
        ex_message_list=[]
        for num,data_line in enumerate(data):
            pass
            #field_index=import_fields.index("input_price")
            #field_val=data_line[field_index]

        if len(ex_message_list)>0:
            return False,ex_message_list
        return True,[]

    def validate_imported_data(self,import_result):
        """
        校验刚刚通过导入的的数据,子类可以重写当前函数,实现自定义的校验过程
        1   第一个表示校验是否成功
        2   错误信息列表,错误信息是包含如下格式dict 的list容器
        {rows:
            {
                "from":1,
                "to":1,
                "message":"Part No Can not be null"
            }
        }
        :return:
        """
        fields=['id','vendor_id','plant_id','part_no','part_no_4','buyer_code','black_white_list','validate_from','validate_to']
        ids=import_result["ids"]
        ex_message_list=[]
        #遍历所有asn_rule
        for item_index,asn_rule_id in enumerate(ids):
            asn_rule_rec=self.env["asn.jitrule"].browse(asn_rule_id)
            if asn_rule_rec.black_white_list=='I001':
                #('I001','I001 INCLUDE BY MATERIAL'),
                if asn_rule_rec.vendor_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type I001 can not specific vendor info"
                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.buyer_code.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type I001 can not specific buyer info"

                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.part_no_4!=False:
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type I001 can not specific Part No First 4 Char"
                    }
                    ex_message_list.append(ex_msg_item)
            if asn_rule_rec.black_white_list=='E001':
                #('E001','E001 EXCLUDE BY VENDOR'),
                if asn_rule_rec.buyer_code.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E001 can not specific buyer info"
                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.plant_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,

                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E001 can not specific plant info"
                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.part_no!=False:
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E001 can not specific part_no"
                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.part_no_4!=False:
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E001 can not specific Part No First 4 Char"
                    }
                    ex_message_list.append(ex_msg_item)
                pass
            if asn_rule_rec.black_white_list=='E002':
                #('E002','E002 EXCLUDE BY VENDOR + MATERIAL'),
                if asn_rule_rec.buyer_code.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E002 can not specific buyer info"
                    }
                    ex_message_list.append(ex_msg_item)

                if asn_rule_rec.part_no_4!=False:
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E002 can not specific Part No First 4 Char"
                    }
                    ex_message_list.append(ex_msg_item)

            if asn_rule_rec.black_white_list=='E003':
                #('E003','E003 EXCLUDE BY MATERIAL'),
                if asn_rule_rec.vendor_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,

                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E003 can not specific vendor info"
                    }
                    ex_message_list.append(ex_msg_item)

                if asn_rule_rec.buyer_code.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,

                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E003 can not specific buyer info"
                    }
                    ex_message_list.append(ex_msg_item)

                if asn_rule_rec.part_no_4!=False:
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,

                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E003 can not specific Part No First 4 Char"
                    }
                    ex_message_list.append(ex_msg_item)

            if asn_rule_rec.black_white_list=='E004':
                #('E004','E004 EXCLUDE BY MATERIAL FIRST 4 CHAR'),
                if asn_rule_rec.vendor_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E004 can not specific vendor info"
                    }
                    ex_message_list.append(ex_msg_item)

                if asn_rule_rec.buyer_code.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E004 can not specific buyer info"
                    }
                    ex_message_list.append(ex_msg_item)

                if asn_rule_rec.part_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                    }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E004 can not specific Part Info"
                    }
                    ex_message_list.append(ex_msg_item)
                if asn_rule_rec.plant_id.exists():
                    ex_msg_vals={
                        "from":item_index,
                        "to":item_index,
                        }
                    ex_msg_item={
                        "rows":ex_msg_vals,
                        "message":"Rule Type E004 can not specific Plant info"
                    }
                    ex_message_list.append(ex_msg_item)
        if len(ex_message_list)==0:
            return True,{}
        else:
            return False,ex_message_list

    @api.multi
    def action_download_file(self):
        file_dir=self.env["muk_dms.directory"].search([('name','=','file_template')],limit=1,order='id desc')
        if not file_dir.exists():
            raise UserError('File dir file_template does not exists!')
        file_template=self.env["muk_dms.file"].search([('filename','=','asn_jit_rule_import.xls')],limit=1,order='id desc')
        if not file_template.exists():
            raise UserError('File Template with name ( %s ) does not exists!'%("asn_jit_rule_import.xls",))
        action = {
            'type': 'ir.actions.act_url',
            'url': '/dms/file/download/%s'%(file_template.id,),
            'target': 'new',
        }
        return action