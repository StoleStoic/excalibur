# Resuming a failed build

A full build takes more than a day on GitHub's runners. When it stops on a
compile error, fix the cause in the patches as usual, and also put the same
change, as a diff against the already-patched source tree, in
`ci/resume-hotfix.patch`. Then start the `build` workflow with
`resume_run_id` set to the failed run's ID. The first stage downloads that
run's saved build tree, applies the hotfix, and continues compiling.

Saved build trees expire four days after they are uploaded. Delete
`resume-hotfix.patch` once a clean build from scratch has succeeded with the
real fix.
