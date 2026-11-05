本次只编写交接给下一个Agent的建筑要求，不实施建模。返回JSON {"summary":"交接要求","project_patch":{...}}。project_patch必须含非空文字name/theme/purpose/layout/circulation/style/ceiling/floor/wall/props，可补preserve/extras/footprint；可选size为三个正整数，buildingShape用随附规范键。
明确主题、空间关系、玩家动线、高差与支承、材质角色、装饰主次、保留项和待验证条件。用户明确给出的坐标、尺寸与约束可以保留；没有依据的细节作为建议，不捏造已验证或已批准结论。
不返回operations、boxes、operation_patch、逐块坐标、脚本、NBT或执行结果。具体建模步骤由接收任务的Agent读取真实源、标注和工具接口后编写。不要为了通过格式校验把方案改成一套工具参数。
