/**
 * setup.js — 配置 FenixAgent 源码路径
 *
 * 用法:
 *   node setup.js <FenixAgent源码目录>
 *
 * 示例:
 *   node setup.js D:\chxu\AI中台\Code\FenixAgent\src
 *   node setup.js /home/user/projects/FenixAgent/src
 *
 * 效果:
 *   1. 在项目根目录创建 fenix-source/ 联接，指向目标源码目录
 *   2. unit_tests/ 下的测试通过 tsconfig paths 自动解析
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const LINK_NAME = path.join(__dirname, 'fenix-source');

const targetPath = process.argv[2];

if (!targetPath) {
  console.log('用法: node setup.js <FenixAgent源码src目录>');
  console.log('');
  console.log('示例:');
  console.log('  node setup.js D:\\chxu\\AI中台\\Code\\FenixAgent\\src');
  console.log('  node setup.js /home/user/projects/FenixAgent/src');
  console.log('');

  // 显示当前状态
  try {
    const stat = fs.lstatSync(LINK_NAME);
    if (stat.isSymbolicLink()) {
      const target = fs.readlinkSync(LINK_NAME);
      console.log(`当前联接: fenix-source -> ${target}`);
    }
  } catch {
    console.log('当前状态: 未配置 (fenix-source 不存在)');
  }
  process.exit(0);
}

// 验证目标目录存在
const resolvedTarget = path.resolve(targetPath);
if (!fs.existsSync(resolvedTarget)) {
  console.error(`错误: 目录不存在 — ${resolvedTarget}`);
  process.exit(1);
}

// 检查是否是有效的 src 目录
const testFile = path.join(resolvedTarget, 'errors.ts');
if (!fs.existsSync(testFile)) {
  console.warn(`警告: ${resolvedTarget} 中没有找到 errors.ts，确认这是 FenixAgent 的 src 目录吗？`);
}

// 删除已存在的联接/目录
try {
  const stat = fs.lstatSync(LINK_NAME);
  if (stat.isSymbolicLink() || stat.isDirectory()) {
    fs.rmSync(LINK_NAME, { recursive: true, force: true });
    console.log(`已删除旧的 fenix-source`);
  }
} catch {
  // 不存在，无需删除
}

// 创建联接 (Windows: mklink /J, Linux/Mac: ln -s)
const isWindows = process.platform === 'win32';
try {
  if (isWindows) {
    execSync(`mklink /J "${LINK_NAME}" "${resolvedTarget}"`, { stdio: 'pipe' });
  } else {
    fs.symlinkSync(resolvedTarget, LINK_NAME, 'dir');
  }
  console.log('');
  console.log(`配置成功!`);
  console.log(`  fenix-source -> ${resolvedTarget}`);
  console.log('');
  console.log('验证: cd unit_tests && bun test');
} catch (err) {
  console.error(`创建联接失败: ${err.message}`);
  if (isWindows) {
    console.error('提示: 如果使用符号链接而非联接，需要以管理员身份运行');
  }
  process.exit(1);
}
