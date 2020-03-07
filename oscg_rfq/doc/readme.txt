---------------存疑问题
1	手动新增rfq的价格和交易条件的来源是什么
    与供应商协商的结果
2	修改已经存在的rfq的限制条件是什么
    不存在限制，等于录入商谈好的价格
3   material_master中存在buyer_code,是不是意味着每一个材料要分管给一个采购
4   料号中的buyer_code是由SAP系统进行更新吗,还是ep系统可以自主更新
5   新增的rfq和已经存在的rfq之间是什么关系
6   rfq修改的业务逻辑是什么
7   下载rfq填写交易条件之后再次上传，这种rfq如何处理是否需要重新签核
8   下载rfq之前是否需要查询对数据进行筛选，操作过程需要确定
9   rfq的批量上传是否只能新建rfq,不能更新已经存在的rfq
10  久未异动的rfq批量新建的规则
    EP系统能够配置时间范围阈值天数
    EP系统能够定时执行或者手工触发任务
    假定阈值天数为120天
    系统获取120天内未降价的rfq
        如果某个材料为新材料，判断标准为rfq表中只有120天之前只有1条记录，这种材料排除在外
    获取到的rfq数据放置到中间表中,状态默认为C,表示初始化状态
    数据产生后BUYER也可以设定 MASS RFQ 状态(对于状态为C的MASS RFQ)
        设定为Y状态的时候,Y表示要建立RFQ，需要输入新单价，有效期，有效期长度不能超过731天,MASS RFQ状态会是 PROCESSING ,建立新rfq后 MASS RFQ 状态为DONE
        设定为N状态的时候,N表示不会降价，要输入原因，并输入memo备注信息,完成后 MASS RFQ 状态为DONE
    数据产生后CM可以设定rfq为N状态(对于状态为C的MASS RFQ)，N表示不会降价，要输入原因，并输入memo备注信息，完成后 MASS RFQ 状态为DONE

-----算法-----
首先要获取材料列表,通过material_master表进行遍历按照记录顺序进行分组,例如每组1000条记录
调用存储过程判断一组材料是否久未异动,传入分组信息例如 limit 1000 offset 2000
对组内的一个特定材料判断是否久未异动,存在久未异动的情况,那么输出数据到rfq_mass表中

---------------功能缺陷
1	单笔新增rfq的情况下,看不到自己的历史新增数据，也就是没有列表视图
2	单笔新增frq的情况下,料号要手动输入，不能查询输入 无需处理
3	修改rfq的情况下，不能通过查询已经存在的rfq后进行修改
4	上传的excel文件导入rfq数据缺少中间存储信息 已经处理
5	不能下载rfq并且填写交易条件上传 已经处理
6	as上传的rfq不能取消


-----buyer_code的来源
class ResPartner(models.Model):
    _inherit = "res.partner"

    employee_code = fields.Char(string="Employee Code")
    buyer_code = fields.Many2many('buyer.code', string="Buyer Code")
    plant_ids = fields.Many2many('pur.org.data', string="Plant")
    is_approver = fields.Boolean(string="Is Approve")

1 月13 2月 20
2月3日 上班



权限配置说明
设置访问权限和记录规则时都在自定义用户组上设置，不在odoo原用户组上设置。
系统内部user和外部user分别设置用户组
系统内部user：group_ep_user，继承自base.group_user。该用户组是系统内部用户组的根用户组。系统内部操作员都从该用户组继承，给该用户组设置了访问权限，从该用户组继承的用户组也都有了相应的权限
系统外部user：IAC_vendor_groups，继承自base.group_user

EP系统管理员：group_ep_administration，从group_ep_user继承

buyer用户组：IAC_buyer_groups，从group_ep_user继承



------------临时工作
--测试数据
/*
part_no 100001700000
part_id		5001
plant_id	104
*/
select T .plant_id,
					T .vendor_id,
					T .part_id,
					T .part_no,
					T .currency_id,
					T .price,
					T .valid_from,
					T .valid_to,
					T .price_control,
					T.ltime,
					T .moq,
					T .mpq,
					T .rw,
					T .cw,
					T .taxcode,
					T .price_unit, t.* from inforecord_history t order by id;

/*
构造测试的job
*/
select * from iac_rfq_mass_job;


--测试久未异动
SELECT * from
	proc_get_rfq_idle_mass (
		1,
		1000,
		0
	)

--查看异常日志
select * from iac_rfq_mass_job_ex order by id desc;


输出sql日志
--log-level=debug_sql

导数据的步骤
po 导入
po change 导入
asn 导入
