#!/usr/bin/env python3
from pathlib import Path
import subprocess

BASE = "87df9fab2d01cbae20896d7bb1f452d3d99ac59c"
TASK = Path("fs/proc/task_mmu.c")
SUSFS = Path("fs/susfs.c")
SYS = Path("kernel/sys.c")
NS = Path("fs/namespace.c")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def base_file(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], text=True)


# task_mmu.c was the conflicted file that got mixed with a different baseline.
# Start from the native 17.0 version, then apply only the SusFS hooks.
task = base_file("fs/proc/task_mmu.c")

task = replace_once(
    task,
    "#include <linux/uaccess.h>\n\n#include <asm/elf.h>",
    "#include <linux/uaccess.h>\n"
    "#if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)\n"
    "#include <linux/susfs_def.h>\n"
    "#endif\n\n"
    "#include <asm/elf.h>",
    "task_mmu SusFS include",
)

task = replace_once(
    task,
    '#include "internal.h"\n\nvoid task_mem',
    '#include "internal.h"\n\n'
    '#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n'
    'extern void susfs_show_map_vma_spoofer(struct inode *inode, dev_t *out_dev, unsigned long *out_ino);\n'
    '#endif\n'
    '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
    'extern int susfs_open_redirect_spoof_show_map_vma(struct inode *inode, unsigned long *out_ino, dev_t *out_dev, char **spoofed_name);\n'
    '#endif\n\n'
    'void task_mem',
    "task_mmu SusFS externs",
)

task = replace_once(
    task,
    "\tdev_t dev = 0;\n\tconst char *name = NULL;\n\n\tif (file) {",
    "\tdev_t dev = 0;\n\tconst char *name = NULL;\n"
    "#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n"
    "\tchar *spoofed_redirected_name = NULL;\n"
    "#endif\n\n"
    "\tif (file) {",
    "task_mmu redirect local",
)

task = replace_once(
    task,
    "\tif (file) {\n"
    "\t\tstruct inode *inode = file_inode(vma->vm_file);\n"
    "\t\tdev = inode->i_sb->s_dev;\n"
    "\t\tino = inode->i_ino;\n"
    "\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n"
    "\t}\n\n"
    "\tstart = vma->vm_start;",
    "\tif (file) {\n"
    "\t\tstruct inode *inode = file_inode(vma->vm_file);\n"
    "#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n"
    "\t\tif (SUSFS_IS_INODE_OPEN_REDIRECT(inode)) {\n"
    "\t\t\tif (!susfs_open_redirect_spoof_show_map_vma(inode, &ino, &dev, &spoofed_redirected_name)) {\n"
    "\t\t\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n"
    "\t\t\t\tgoto orig_flow;\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "#endif\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\t\tif (SUSFS_IS_INODE_SUS_MAP(inode))\n"
    "\t\t\treturn;\n"
    "#endif\n"
    "\t\tdev = inode->i_sb->s_dev;\n"
    "\t\tino = inode->i_ino;\n"
    "\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
    "\t\tsusfs_show_map_vma_spoofer(inode, &dev, &ino);\n"
    "#endif\n"
    "\t}\n\n"
    "#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n"
    "orig_flow:\n"
    "#endif\n\n"
    "\tstart = vma->vm_start;",
    "task_mmu map inode hooks",
)

task = replace_once(
    task,
    "\t/*\n"
    "\t * Print the dentry name for named mappings, and a\n"
    "\t * special [heap] marker for the heap:\n"
    "\t */\n"
    "\tif (file) {",
    "\t/*\n"
    "\t * Print the dentry name for named mappings, and a\n"
    "\t * special [heap] marker for the heap:\n"
    "\t */\n"
    "#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n"
    "\tif (spoofed_redirected_name) {\n"
    "\t\tseq_puts(m, spoofed_redirected_name);\n"
    "\t\tseq_putc(m, '\\n');\n"
    "\t\tkfree(spoofed_redirected_name);\n"
    "\t\treturn;\n"
    "\t}\n"
    "#endif\n"
    "\tif (file) {",
    "task_mmu redirect map name",
)

task = replace_once(
    task,
    "\tbool rollup_mode;\n\tbool last_vma;\n\n\tif (priv->rollup) {",
    "\tbool rollup_mode;\n\tbool last_vma;\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\tbool sus_map = vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file));\n"
    "#endif\n\n"
    "\tif (priv->rollup) {",
    "task_mmu smaps sus_map local",
)

task = replace_once(
    task,
    "\tsmaps_walk.private = mss;\n\n#ifdef CONFIG_SHMEM",
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\t/* Hide marked VMAs from smaps. For rollup, skip their accounting but\n"
    "\t * keep the native iterator so the final visible aggregate is emitted. */\n"
    "\tif (sus_map && !rollup_mode)\n"
    "\t\treturn 0;\n"
    "#endif\n\n"
    "\tsmaps_walk.private = mss;\n\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\tif (sus_map)\n"
    "\t\tgoto skip_smap_stats;\n"
    "#endif\n\n"
    "#ifdef CONFIG_SHMEM",
    "task_mmu smaps skip prelude",
)

task = replace_once(
    task,
    "\t/* mmap_sem is held in m_start */\n"
    "\twalk_page_vma(vma, &smaps_walk);\n\n"
    "\tif (!rollup_mode) {",
    "\t/* mmap_sem is held in m_start */\n"
    "\twalk_page_vma(vma, &smaps_walk);\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "skip_smap_stats:\n"
    "#endif\n\n"
    "\tif (!rollup_mode) {",
    "task_mmu smaps skip label",
)

task = replace_once(
    task,
    "\tunsigned long end_vaddr;\n\tint ret = 0, copied = 0;\n\n\tif (!mm || !mmget_not_zero(mm))",
    "\tunsigned long end_vaddr;\n\tint ret = 0, copied = 0;\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\tstruct vm_area_struct *vma;\n"
    "#endif\n\n"
    "\tif (!mm || !mmget_not_zero(mm))",
    "task_mmu pagemap local",
)

task = replace_once(
    task,
    "\t\tdown_read(&mm->mmap_sem);\n"
    "\t\tret = walk_page_range(start_vaddr, end, &pagemap_walk);\n"
    "\t\tup_read(&mm->mmap_sem);",
    "\t\tdown_read(&mm->mmap_sem);\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "\t\tvma = find_vma(mm, start_vaddr);\n"
    "\t\tif (vma && start_vaddr < vma->vm_start)\n"
    "\t\t\tvma = NULL;\n"
    "\t\tif (vma && vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n"
    "\t\t\tgoto bypass_orig_flow;\n"
    "#endif\n"
    "\t\tret = walk_page_range(start_vaddr, end, &pagemap_walk);\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
    "bypass_orig_flow:\n"
    "#endif\n"
    "\t\tup_read(&mm->mmap_sem);",
    "task_mmu pagemap hook",
)
TASK.write_text(task)

# Fix OPEN_REDIRECT output ownership: the source passed char * by value,
# so the allocated spoofed pathname never reached show_map_vma().
susfs = SUSFS.read_text()
# Allow re-running this script after the first repair commit.
if "char **spoofed_name" not in susfs:
    susfs = replace_once(
        susfs,
        "int susfs_open_redirect_spoof_show_map_vma(struct inode *inode, unsigned long *out_ino, dev_t *out_dev, char *spoofed_name) {",
        "int susfs_open_redirect_spoof_show_map_vma(struct inode *inode, unsigned long *out_ino, dev_t *out_dev, char **spoofed_name) {",
        "susfs redirect signature",
    )
    susfs = replace_once(
        susfs,
        "\tif (spoofed_name) {\n\t\tSUSFS_LOGE(\"spoofed_name must be NULL first!\\n\");\n\t\treturn -EINVAL;\n\t}",
        "\tif (!spoofed_name || *spoofed_name) {\n\t\tSUSFS_LOGE(\"spoofed_name output must be valid and NULL first!\\n\");\n\t\tsrcu_read_unlock(&susfs_srcu_open_redirect, srcu_idx);\n\t\treturn -EINVAL;\n\t}",
        "susfs redirect output validation",
    )
    susfs = replace_once(
        susfs,
        "\t\t\tspoofed_name = kzalloc(SUSFS_MAX_LEN_PATHNAME, GFP_KERNEL);\n\t\t\tif (!spoofed_name) {",
        "\t\t\t*spoofed_name = kzalloc(SUSFS_MAX_LEN_PATHNAME, GFP_KERNEL);\n\t\t\tif (!*spoofed_name) {",
        "susfs redirect allocation",
    )
    susfs = replace_once(
        susfs,
        "\t\t\tstrncpy(spoofed_name, entry->info.redirected_pathname, SUSFS_MAX_LEN_PATHNAME - 1);",
        "\t\t\tstrncpy(*spoofed_name, entry->info.redirected_pathname, SUSFS_MAX_LEN_PATHNAME - 1);",
        "susfs redirect copy",
    )
SUSFS.write_text(susfs)

# kernel/sys.c was another -X theirs conflict. Rebuild it from the native
# target baseline and add only the SusFS uname hook, preserving target fake-uname
# options and the target GMS handling.
sysc = base_file("kernel/sys.c")
sysc = replace_once(
    sysc,
    "SYSCALL_DEFINE1(newuname, struct new_utsname __user *, name)\n{",
    "#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME\n"
    "extern void susfs_spoof_uname(struct new_utsname *tmp);\n"
    "#endif\n"
    "SYSCALL_DEFINE1(newuname, struct new_utsname __user *, name)\n{",
    "sys uname extern",
)
sysc = replace_once(
    sysc,
    "#endif\n\tup_read(&uts_sem);\n\n\trcu_read_lock();",
    "#endif\n"
    "#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME\n"
    "\tsusfs_spoof_uname(&tmp);\n"
    "#endif\n"
    "\tup_read(&uts_sem);\n\n"
    "\trcu_read_lock();",
    "sys uname hook",
)
SYS.write_text(sysc)

# namespace.c largely applied, but two native target allocator functions were
# overwritten by the source baseline. Keep all SusFS additions and restore the
# target's IDA locking/start semantics with SusFS-specific exceptions.
ns = NS.read_text()
old_free_start = ns.index("static void mnt_free_id(struct mount *mnt)\n{")
old_free_end = ns.index("\n}\n\n/*\n * Allocate a new peer group ID", old_free_start) + 2
ns = ns[:old_free_start] + """static void mnt_free_id(struct mount *mnt)
{
	int id = mnt->mnt_id;
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	if (mnt->mnt.mnt_flags & VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT)
		return;
#endif
	spin_lock(&mnt_id_lock);
	ida_remove(&mnt_id_ida, id);
	if (mnt_id_start > id)
		mnt_id_start = id;
	spin_unlock(&mnt_id_lock);
}""" + ns[old_free_end:]

alloc_start = ns.index("static int mnt_alloc_group_id(struct mount *mnt)\n{")
alloc_end = ns.index("\n}\n\n/*\n * Release a peer group ID", alloc_start) + 2
ns = ns[:alloc_start] + """static int mnt_alloc_group_id(struct mount *mnt)
{
	int res;
	int start = mnt_group_start;
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	bool ksu_group = susfs_is_current_ksu_domain();

	if (ksu_group)
		start = DEFAULT_KSU_MNT_GROUP_ID;
#endif

	if (!ida_pre_get(&mnt_group_ida, GFP_KERNEL))
		return -ENOMEM;

	res = ida_get_new_above(&mnt_group_ida, start, &mnt->mnt_group_id);
	if (!res) {
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
		if (!ksu_group)
#endif
			mnt_group_start = mnt->mnt_group_id + 1;
	}

	return res;
}""" + ns[alloc_end:]
NS.write_text(ns)

# Structural sanity checks for the files hit by automatic conflict resolution.
fixed = TASK.read_text()
if fixed.count("static int show_smap(struct seq_file *m, void *v, int is_pid)") != 1:
    raise RuntimeError("native show_smap signature missing or duplicated")
if "static int show_smap(struct seq_file *m, void *v)" in fixed:
    raise RuntimeError("foreign show_smap implementation still present")
if "static int show_smaps_rollup(" in fixed:
    raise RuntimeError("foreign smaps_rollup implementation still present")
if "SEQ_PUT_DEC" in fixed:
    raise RuntimeError("foreign task_mmu baseline residue still present")

sysfixed = SYS.read_text()
if "CONFIG_FAKE_UNAME_4_19" not in sysfixed or "susfs_spoof_uname(&tmp);" not in sysfixed:
    raise RuntimeError("kernel/sys.c target fake-uname flow or SusFS hook missing")

nsfixed = NS.read_text()
if "spin_lock(&mnt_id_lock);" not in nsfixed or "ida_get_new_above(&mnt_group_ida, start" not in nsfixed:
    raise RuntimeError("fs/namespace.c native allocator semantics not restored")

print("SusFS conflicted files repaired against native 17.0 semantics")
