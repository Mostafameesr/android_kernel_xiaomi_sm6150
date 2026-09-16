#!/usr/bin/env python3
from pathlib import Path
import subprocess

BASE = "87df9fab2d01cbae20896d7bb1f452d3d99ac59c"
path = Path("fs/open.c")
text = subprocess.check_output(["git", "show", f"{BASE}:fs/open.c"], text=True)

def repl(old, new, label):
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one match, got {n}")
    text = text.replace(old, new, 1)

repl(
    "#include <linux/compat.h>\n\n#include \"internal.h\"",
    "#include <linux/compat.h>\n#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n#include <linux/susfs_def.h>\n#endif\n\n#include \"internal.h\"",
    "include",
)
repl(
    "EXPORT_SYMBOL(filp_clone_open);\n\nlong do_sys_open",
    "EXPORT_SYMBOL(filp_clone_open);\n\n#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\nextern struct filename *susfs_open_redirect_spoof_do_sys_openat(struct inode *inode);\n#endif\n\nlong do_sys_open",
    "extern",
)
repl(
    "\tstruct filename *tmp;\n\n\tif (fd)",
    "\tstruct filename *tmp;\n#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\tstruct filename *fake_filename = NULL;\n\tbool is_inode_open_redirect = false;\n#endif\n\n\tif (fd)",
    "locals",
)
repl(
    "\tfd = get_unused_fd_flags(flags);\n\tif (fd >= 0) {",
    "\tfd = get_unused_fd_flags(flags);\n#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\nretry:\n#endif\n\tif (fd >= 0) {",
    "retry",
)
repl(
    "\t\tstruct file *f = do_filp_open(dfd, tmp, &op);\n\t\tif (IS_ERR(f) && !libperfmgr_redirect(&f, dfd, tmp, &op, flags)) {",
    "\t\tstruct file *f = do_filp_open(dfd, tmp, &op);\n#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\t\tif (!is_inode_open_redirect && f && !IS_ERR(f)) {\n\t\t\tstruct inode *inode = file_inode(f);\n\t\t\tif (SUSFS_IS_INODE_OPEN_REDIRECT_WITHOUT_UID_CHECK(inode)) {\n\t\t\t\tfake_filename = susfs_open_redirect_spoof_do_sys_openat(inode);\n\t\t\t\tif (fake_filename && !IS_ERR(fake_filename)) {\n\t\t\t\t\tis_inode_open_redirect = true;\n\t\t\t\t\tfilp_close(f, NULL);\n\t\t\t\t\tputname(tmp);\n\t\t\t\t\ttmp = fake_filename;\n\t\t\t\t\tgoto retry;\n\t\t\t\t}\n\t\t\t}\n\t\t}\n#endif\n\t\tif (IS_ERR(f) && !libperfmgr_redirect(&f, dfd, tmp, &op, flags)) {",
    "redirect integration",
)

if "libperfmgr_redirect(&f, dfd, tmp, &op, flags)" not in text:
    raise RuntimeError("native libperfmgr_redirect flow lost")
if "susfs_open_redirect_spoof_do_sys_openat" not in text:
    raise RuntimeError("SusFS open redirect hook missing")
path.write_text(text)
print("fs/open.c rebuilt from native target with SusFS redirect layered on top")
