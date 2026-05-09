-- 为 ods_attendance_summary 表添加 overtime_2030_count 字段
-- 执行此脚本前请确保已备份数据

ALTER TABLE ods_attendance_summary 
ADD COLUMN overtime_2030_count INT DEFAULT 0 COMMENT '20:30以后加班次数（月度汇总）';

-- 验证字段是否添加成功
DESC ods_attendance_summary;
