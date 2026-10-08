# F2b first independent review / repair audit

Initial disposition: **CHANGES_REQUIRED** for seven reproduced verifier defects. Actual candidate05/fault06 artifacts independently support modeled task PASS/FAIL under their fixed recipe; no teacher-training acceptance, hardware, continuousM5 or risk certification. Reviewer never authored F2b, no production/source edits/commits/GPU/download/API/key/.env access. Reused independent reviewer context under local AGENTS quota.

## Initial findings and fixture correction

`tests/review_f2b_gates.py`, initial log `runs/implementation_20261005/review_F2B_20261006T0020/adversarial.log`:8 failures in7.09s. **Seven are actual producer/verifier defects; eighth mixed-Boolean case initially failed an incorrect reviewer precondition**, not an observed falsePASS. Actual first qdot component is3.395785713e-7, not exactzero. Removed only that precondition, strengthened direct check_snapshot UNKNOWN requirement so numeric zero within bounds cannot close the test through replay-tolerance failure. Original log preserved, no author hardzero or altered physics.

Actual short unassisted3-command/75-step physicalPASS records expose:

- Stored substep qdot differing from actual fullqvel still PASS; object linear velocity mismatch likewise PASS. Replay compared fullqpos/qvel but not derived fields consumed by velocity/task gates.
- Initial T+1 boundary assistanceTrue or wrong TCP rotation still PASS because initial boundary checked only four fields; entire initial boundary must bind real initial snapshot.
- Issued command modevelocity/holdlinear and descriptor unitsdegree still PASS; action/controller/robot semantic metadata must match frozen native recipe.
- Mixed Boolean goal vector[False,.1,.018] was coerced to physicalscalar rather than rejected. Corrected mixed-Boolean velocity case additionally requires type rejection before coercion, not numeric mismatch.

Root/original author notified; production fixes in progress during later work. Some later tests therefore ran intermediate code: author original8 cases7pass/1reason-string failure (NONREAL_OR_BOOLEAN_COMMAND vs generic malformed), and real15-command speed-forgery probe became UNKNOWN after new readback guard. These are retained but **not** claimed final acceptance. Final stable-code retest/provenance section will supersede initial disposition only after actual replay.

## Independent actual artifact replay / mathematical readback

Owned evidence `actual_audits.json` / `actual_audits_second.log`. Actual source05 and06 each280commands/281states/14s and **7,000 independently replayed physical substeps**; source files read SHA before/after unchanged. Rebuilt exact original parameters/MJCF using preserved integer/float lexemes. Initial reviewer harness passed metadata sceneid as constructor arg (TypeError before physics), fixed by selecting only four real scene parameters; failed harness log retained.

Candidate05 audit PASS / taskSATISFIED; fault06 physicalPASS / taskFAIL / overallFAIL. Independent derived-field recomputation across every stored substep: q=qpos[index], qdot=qvel[index], objectlinearv=qvel free translation all maxerror0, WORLDangular=R(objectquat)×localfreeangular maxerror4.44e-15(candidate05)/1.78e-15(fault06). Both actual records contain no Boolean values in these physical vectors. Independent extra computations do not validate unsafe acceptance of altered records; they show retained data itself is consistent.

Candidate05 actual maxima: penetration1.414478mm<2mm; fixed/moving aggregate pad forces45.5801/43.3205N<60N; support30.0365N<100N; joint speed2.668128<3rad/s; native torque2.94Nm; unintendedcontact samples0; replayerror0. Recipe thresholds are preregistered DEVELOPMENT SIM_ASSUMPTION, not hardware measurements. Original native contact/adjacent filtering unchanged; 500Hz sampling is not universal collision/continuous interval proof. Sourcegoal/initial/controller same registeredA scenario; no object assistance, weld or trajectory script in replay.

## Actual image/state and source denominators

`image_state_readback.json` / `image_readback.log`: both exports281 actualRGB states plus1 explicit zero-padding image (282 unique hashes each), all actual PNG320×240 uint8 hashes and previous/current history links verified; masks[false,true] then[true,true], each boundary sourceindex/time/q matches retained execution. Primary internal NPZ shape281×107, Boolean masks43true perrow, unusedslots/articulations false; commands280 and all281 timestamps exact. **NPZ is internal numeric evidence, not LeRobot.** Teacher training accepted remainsfalse; known older teacher05 manifest has no kind field, status explicitly candidate/pending; fault06 rawfailed status preserved. No video/RGB/model rerun or privateRGB upload.

Preregistered32slots, attempted6, remaining26 NOT_RUN; four actualfull episodes and two localIK planning failures/no controls; one correlated original source/initialscenario group. Attempts01/03/05/06 and failure02/04 preserved; no4/6 robot success estimate, repeated audits/rendering do not create independent groups. Original01 11depth violations not repaired by relaxing2mm recipe. Controller amendments are discovery outside default boundedM4 repair claims. Candidate06 open-gripper fault actual taskfailure and46.56mm opening gap not clipped into legal bounded teacher. Reference-corruption .5mm is clearly nonexecuted label corruption.

## Initial review commands / isolation

Cwd `/home/xklv/ego_robot/a4_experiment`, .venv-runtime/bin/python -B, PYTHONDONTWRITEBYTECODE/PYTHONPATHsrc, CPUOMP/MKL2, absolute local TMP/XDG/UV/PIP/HF/TORCH/MPL, local OSMesa LD_LIBRARY_PATH/MUJOCO_GL=osmesa. Unique reviewer basetemp/run, no source modifications.

```
.venv-runtime/bin/python -B -m pytest tests/review_f2b_gates.py -q -p no:cacheprovider --basetemp=$PWD/.runtime/tmp/review_F2B0020
.venv-runtime/bin/python -B -m pytest tests/test_sim_teacher_gates.py -q -p no:cacheprovider --basetemp=$PWD/.runtime/tmp/review_F2B_original0021
```

Actual audit uses fixed05/06 refs, expectedmodel signatures, real MuJoCo independent replay and separately computed derived fields; source/image readbacks readonly. Final verified codeSHA and corrected eight cases/actual replay under stable author fixes still required before any scope acceptance. All findings reported, author-only fixes; no self-issued teacher flag.

## Stable repaired verifier: final independent scope closure

After author stable/HOLD notice, corrected reviewer8 + author gate8: **16 passed in25.13s**, exit0, `runs/implementation_20261005/review_F2B_final_20261006T0030/tests.log`. Reviewer mixed-Boolean branch now checks direct bounds-checker UNKNOWN before replay, so numeric tolerance cannot disguise Boolean coercion. Command mode/hold/units, all initial/subsequent boundaries, derived fields/fullreplay and pre-cast types close original seven defects. Preserved initial failures and fixture correction remain above. No reviewer production edits.

Independently replayed both actual05/06 again using **only immutable validator/dependency snapshot** `backups/F2b_validator_fixed_20261005T134912_816871/source/src`, explicit readonly original model_root. Gate source SHA **73634a25a197dd9dd0518968187442a052ab9d6f824e04a4622604aee7daf7a9**. Import path asserted inside that snapshot. Each7,000 substeps/replayerror0/sourceunchanged;05PASS/taskSATISFIED,06physicalPASS/taskFAIL. `frozen_actual_audits.json` and log record actual computed outcomes, timing, refs and immutable validator_source, separate from historical producer. This is numerical recomputation, not a supplied PASS receipt.

Final disposition supersedes initial CHANGES_REQUIRED: **ACCEPTED for tested SO101 fixed-scene, unassisted actual T1 / 500Hz estimated-model recipe and immutable numeric replay/readback scope only.** Candidate05 is a numerically audited modeled teacher candidate; fault06 is genuine paired modeled taskfailure. No physical success in original ego/real hardware, continuous-between-stepM5 proof, risk certificate, unobserved scenes/seeds/robots or formal policy gain. One correlated source group remainsone, not7,000samples. Existing teacher_training_acceptedfalse untouched; root/evidence compiler must bind this independent review and numeric snapshot before qualified masks/training export, rather than toggle a Boolean by itself.

All10 current reviewed production/dependency/tool hashes plus actual official model HEAD/clean status saved `review_F2B_final_20261006T0030/reviewed_source_hashes.json`; model HEAD4d038b3feae26ec82b46a4d586379114012a8ac7 clean. Actualsource05/06 and image artifacts remainedread-only. Root must check unchanged SHA before publishing snapshot/qualified integration.

Final command uses same isolated CPU/runtime/OSMesa/local cache environment above:

```
.venv-runtime/bin/python -B -m pytest tests/review_f2b_gates.py tests/test_sim_teacher_gates.py -q -p no:cacheprovider --basetemp=$PWD/.runtime/tmp/review_F2B_final0030
```

Frozen replay command uses PYTHONPATH=$PWD/backups/F2b_validator_fixed_20261005T134912_816871/source/src and calls audit_artifact with actual execution/summary refs, allowedroots originalroot, expectedmodel signature and model_root=originalroot; outcomes saved only new owned reviewrun. No source/asset/download/global-driver/API/GPU/credential operations.
