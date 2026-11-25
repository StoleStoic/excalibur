# Resuming a failed build

A full build takes more than a day on GitHub's runners. When it stops on a
compile error, fix the cause in the patches as usual, and also put the same
change, as a diff against the already-patched source tree, in
`ci/resume-hotfix.patch`. Then start the `build` workflow with
`resume_run_id` set to the failed run's ID. The first stage downloads that
run's saved build tree, applies the hotfix, and continues compiling.

Saved build trees expire four days after they are uploaded. The hotfix is
relative to the saved tree being resumed, so delete `resume-hotfix.patch`
once the real fix is in the patches and before starting a build from scratch.
