args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("usage: run_rfvs.R <keyfile> <fvs-bin> <library-root>")
}

keyfile <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
fvs_bin <- normalizePath(args[[2]], winslash = "/", mustWork = TRUE)
library_root <- normalizePath(args[[3]], winslash = "/", mustWork = TRUE)
.libPaths(library_root)

library(rFVS)
fvsLoad("FVSsn", fvs_bin)
fvsSetCmdLine(paste0("--keywordfile=", keyfile))

repeat {
  return_code <- fvsRun()
  if (return_code == 2) {
    break
  }
  if (return_code != 0) {
    stop(paste("FVS returned", return_code))
  }
}

cat("FVS run completed\n")
