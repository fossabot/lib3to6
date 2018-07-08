# This file is part of the three2six project
# https://github.com/mbarkhau/three2six
# (C) 2018 Manuel Barkhau <mbarkhau@gmail.com>
#
# SPDX-License-Identifier:    MIT

import sys
import ast
import typing as typ

from . import common


class VersionInfo:

    apply_since: str
    apply_until: str
    works_since: str
    works_until: typ.Optional[str]

    def __init__(
        self, apply_since: str, apply_until: str, works_since: str=None, works_until: str=None,
    ) -> None:

        self.apply_since = apply_since
        self.apply_until = apply_until
        if works_since is None:
            # Implicitly, if it's applied since a version, it
            # also works since then.
            self.works_since = self.apply_since
        else:
            self.works_since = works_since
        self.works_until = works_until


class FixerBase:

    version_info: VersionInfo

    def __init__(self):
        self.required_imports: typ.Set[common.ImportDecl] = set()

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        raise NotImplementedError()

    def is_required_for(self, version):
        nfo = self.version_info
        return nfo.apply_since <= version <= nfo.apply_until

    def is_compatible_with(self, version):
        nfo = self.version_info
        return (
            nfo.works_since <= version and (
                nfo.works_until is None or version <= nfo.works_until
            )
        )


class TransformerFixerBase(FixerBase, ast.NodeTransformer):

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        return self.visit(tree)


# NOTE (mb 2018-06-24): Version info pulled from:
# https://docs.python.org/3/library/__future__.html


class FutureImportFixerBase(FixerBase):

    future_name: str

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        self.required_imports.add(("__future__", self.future_name))
        return tree


class GeneratorStopFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="3.5",
        apply_until="3.6",
    )

    future_name = "generator_stop"


class UnicodeLiteralsFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.6",
        apply_until="2.7",
    )

    future_name = "unicode_literals"


class PrintFunctionFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.6",
        apply_until="2.7",
    )

    future_name = "print_function"


class WithStatementFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.5",
        apply_until="2.5",
    )

    future_name = "with_statement"


class AbsoluteImportFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.5",
        apply_until="2.7",
    )

    future_name = "absolute_import"


class DivisionFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.2",
        apply_until="2.7",
    )

    future_name = "division"


class GeneratorsFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.2",
        apply_until="2.2",
    )

    future_name = "generators"


class NestedScopesFutureFixer(FutureImportFixerBase):

    version_info = VersionInfo(
        apply_since="2.1",
        apply_until="2.1",
    )

    future_name = "nested_scopes"


class RangeToXrangeFixer(FixerBase):

    version_info = VersionInfo(
        apply_since="1.0",
        apply_until="2.7",
    )

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name):
                continue

            if node.id == "range" and isinstance(node.ctx, ast.Load):
                node.id = "xrange"

        return tree


class RemoveFunctionDefAnnotationsFixer(FixerBase):

    version_info = VersionInfo(
        apply_since="1.0",
        apply_until="2.7",
    )

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            node.returns = None
            for arg in node.args.args:
                arg.annotation = None
            for arg in node.args.kwonlyargs:
                arg.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation = None

        return tree


class RemoveAnnAssignFixer(TransformerFixerBase):

    version_info = VersionInfo(
        apply_since="1.0",
        apply_until="3.5",
    )

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign:
        name_node = node.target
        if not isinstance(name_node, ast.Name):
            raise Exception(f"Unexpected Node Type {name_node}")

        value: ast.expr
        if node.value is None:
            value = ast.NameConstant(value=None)
        else:
            value = node.value
        return ast.Assign(targets=[name_node], value=value)


class ShortToLongFormSuperFixer(TransformerFixerBase):

    version_info = VersionInfo(
        apply_since="2.2",
        apply_until="2.7",
    )

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        for maybe_method in ast.walk(node):
            if not isinstance(maybe_method, ast.FunctionDef):
                continue
            method: ast.FunctionDef = maybe_method
            method_args: ast.arguments = method.args
            if len(method_args.args) == 0:
                continue
            self_arg: ast.arg = method_args.args[0]

            for maybe_super_call in ast.walk(method):
                if not isinstance(maybe_super_call, ast.Call):
                    continue
                func_node = maybe_super_call.func
                if not (isinstance(func_node, ast.Name) and func_node.id == "super"):
                    continue
                super_call = maybe_super_call
                if len(super_call.args) > 0:
                    continue

                super_call.args = [
                    ast.Name(id=node.name, ctx=ast.Load()),
                    ast.Name(id=self_arg.arg, ctx=ast.Load()),
                ]
        return node


class InlineKWOnlyArgsFixer(TransformerFixerBase):

    version_info = VersionInfo(
        apply_since="1.0",
        apply_until="3.5",
    )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if not node.args.kwonlyargs:
            return node

        if node.args.kwarg:
            kw_name = node.args.kwarg.arg
        else:
            kw_name = "kwargs"
            node.args.kwarg = ast.arg(arg=kw_name, annotation=None)

        # NOTE (mb 2018-06-03): Only use defaults for kwargs
        #   if they are literals. Everything else would
        #   change the semantics too much and so we should
        #   raise an error.
        kwonlyargs = reversed(node.args.kwonlyargs)
        kw_defaults = reversed(node.args.kw_defaults)
        for arg, default in zip(kwonlyargs, kw_defaults):
            arg_name = arg.arg
            if default is None:
                new_node = ast.Assign(
                    targets=[ast.Name(id=arg_name, ctx=ast.Store())],
                    value=ast.Subscript(
                        value=ast.Name(id=kw_name, ctx=ast.Load()),
                        slice=ast.Index(value=ast.Str(s=arg_name)),
                        ctx=ast.Load(),
                    )
                )
            else:
                if not isinstance(default, IMMUTABLE_EXPR_TYPES):
                    raise Exception(
                        f"Keyword only arguments must be immutable. "
                        f"Found: {default} on {default.lineno}:{node.col_offset} for {arg_name}"
                    )

                new_node = ast.Assign(
                    targets=[ast.Name(
                        id=arg_name,
                        ctx=ast.Store(),
                    )],
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=kw_name, ctx=ast.Load()),
                            attr="get",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Str(s=arg_name), default],
                        keywords=[],
                    )
                )

            node.body.insert(0, new_node)

        node.args.kwonlyargs = []

        return node


if sys.version_info >= (3, 6):

    class FStringToStrFormatFixer(TransformerFixerBase):

        version_info = VersionInfo(
            apply_since="2.6",
            apply_until="3.5",
        )

        def _formatted_value_str(
            self,
            fmt_val_node: ast.FormattedValue,
            arg_nodes: typ.List[ast.expr],
        ) -> str:
            arg_index = len(arg_nodes)
            arg_nodes.append(fmt_val_node.value)

            format_spec_node = fmt_val_node.format_spec
            if format_spec_node is None:
                format_spec = ""
            elif not isinstance(format_spec_node, ast.JoinedStr):
                raise Exception(f"Unexpected Node Type {format_spec_node}")
            else:
                format_spec = ":" + self._joined_str_str(format_spec_node, arg_nodes)

            return "{" + str(arg_index) + format_spec + "}"

        def _joined_str_str(
            self,
            joined_str_node: ast.JoinedStr,
            arg_nodes: typ.List[ast.expr],
        ) -> str:
            fmt_str = ""
            for val in joined_str_node.values:
                if isinstance(val, ast.Str):
                    fmt_str += val.s
                elif isinstance(val, ast.FormattedValue):
                    fmt_str += self._formatted_value_str(val, arg_nodes)
                else:
                    raise Exception(f"Unexpected Node Type {val}")
            return fmt_str

        def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.Call:
            arg_nodes: typ.List[ast.expr] = []

            fmt_str = self._joined_str_str(node, arg_nodes)
            format_attr_node = ast.Attribute(
                value=ast.Str(s=fmt_str),
                attr="format",
                ctx=ast.Load(),
            )
            return ast.Call(func=format_attr_node, args=arg_nodes, keywords=[])


class NewStyleClassesFixer(TransformerFixerBase):

    version_info = VersionInfo(
        apply_since="2.0",
        apply_until="2.7",
    )

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if len(node.bases) == 0:
            node.bases.append(ast.Name(id="object", ctx=ast.Load()))
        return node


class ItertoolsBuiltinsFixer(TransformerFixerBase):

    version_info = VersionInfo(
        apply_since="2.0",
        apply_until="2.7",
    )

    # WARNING (mb 2018-06-09): This fix is very broad, and should
    #   only be used in combination with a sanity check that the
    #   builtin names are not being overridden.

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        return self.visit(tree)

    def visit_Name(self, node: ast.Name) -> typ.Union[ast.Name, ast.Attribute]:
        if node.id not in ("map", "zip", "filter"):
            return node

        self.required_imports.add(("itertools", None))

        return ast.Attribute(
            value=ast.Name(id="itertools", ctx=ast.Load()),
            attr="i" + node.id,
            ctx=ast.Load(),
        )


class BlockNode:

    body: typ.List[ast.stmt]


STMTLIST_FIELD_NAMES = {"body", "orelse", "finalbody"}


def node_field_sort_key(elem):
    # NOTE (mb 2018-06-23): Expand block bodies before
    #   node expressions There's no particular reason to
    #   do this other than making things predictable (and
    #   testable).
    field_name, field = elem
    return (field_name not in STMTLIST_FIELD_NAMES, field_name)


ArgUnpackNodes = (ast.Call, ast.List, ast.Tuple, ast.Set)
ArgUnpackType = typ.Union[ast.Call, ast.List, ast.Tuple, ast.Set]
KwArgUnpackNodes = (ast.Call, ast.Dict)
KwArgUnpackType = typ.Union[ast.Call, ast.Dict]

ValNodeUpdate = typ.Tuple[typ.List[ast.stmt], ast.expr, typ.List[ast.Delete]]
ListFieldNodeUpdate = typ.Tuple[typ.List[ast.stmt], typ.List[ast.expr], typ.List[ast.Delete]]
ExpandedUpdate = typ.Tuple[typ.List[ast.stmt], typ.List[ast.Delete]]


def is_block_field(field_name: str, field: typ.Any) -> bool:
    return field_name in STMTLIST_FIELD_NAMES and isinstance(field, list)


def make_temp_lambda_as_def(
    lambda_node: ast.Lambda, body: typ.List[ast.stmt], name="temp_lambda_as_def"
) -> ast.FunctionDef:
    body.append(ast.Return(value=lambda_node.body))
    return ast.FunctionDef(name=name, args=lambda_node.args, body=body, decorator_list=[])


class UnpackingGeneralizationsFixer(FixerBase):

    version_info = VersionInfo(
        apply_since="2.0",
        apply_until="3.4",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tmp_var_index = 0

    def has_args_unpacking(self, val_node: ast.expr) -> bool:
        if isinstance(val_node, ast.Call):
            elts = val_node.args
        elif isinstance(val_node, (ast.List, ast.Tuple, ast.Set)):
            elts = val_node.elts
        else:
            raise TypeError(f"Unexpected val_node: {val_node}")

        has_starred_arg = False
        for arg in elts:
            # Anything after * means we have to apply the fix
            if has_starred_arg:
                return True
            has_starred_arg = isinstance(arg, ast.Starred)
        return False

    def has_kwargs_unpacking(self, val_node: ast.expr) -> bool:
        if isinstance(val_node, ast.Call):
            has_kwstarred_arg = False
            for kw in val_node.keywords:
                if has_kwstarred_arg:
                    # Anything after ** means we have to apply the fix
                    return True
                has_kwstarred_arg = kw.arg is None
            return False
        elif isinstance(val_node, ast.Dict):
            has_kwstarred_arg = False
            for key in val_node.keys:
                if has_kwstarred_arg:
                    # Anything after ** means we have to apply the fix
                    return True
                has_kwstarred_arg = key is None
            return False
        else:
            raise TypeError(f"Unexpected val_node: {val_node}")

    def expand_args_unpacking(self, val_node: ArgUnpackType) -> ValNodeUpdate:
        upg_args_name = f"upg_args_{self._tmp_var_index}"
        self._tmp_var_index += 1

        prefix_nodes: typ.List[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=upg_args_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        ]

        if isinstance(val_node, ast.Call):
            new_val_func = val_node.func
            new_val_keywords = val_node.keywords
            elts = val_node.args
        elif isinstance(val_node, (ast.List, ast.Tuple, ast.Set)):
            func_id = val_node.__class__.__name__.lower()
            assert func_id in ("list", "tuple", "set")
            new_val_func = ast.Name(id=func_id, ctx=ast.Load())
            new_val_keywords = []
            elts = val_node.elts
        else:
            raise TypeError(f"Unexpected val_node: {val_node}")

        for arg in elts:
            if isinstance(arg, ast.Starred):
                func_name = "extend"
                args = [arg.value]
            else:
                func_name = "append"
                args = [arg]

            func_node = ast.Attribute(
                value=ast.Name(id=upg_args_name, ctx=ast.Load()),
                attr=func_name,
                ctx=ast.Load(),
            )
            prefix_nodes.append(ast.Expr(
                value=ast.Call(func=func_node, args=args, keywords=[])
            ))

        new_val_node = ast.Call(
            func=new_val_func,
            args=[ast.Starred(
                value=ast.Name(id=upg_args_name, ctx=ast.Load()),
                ctx=ast.Load(),
            )],
            keywords=new_val_keywords,
        )
        del_node = ast.Delete(targets=[ast.Name(id=upg_args_name, ctx=ast.Del())])
        return prefix_nodes, new_val_node, [del_node]

    def expand_kwargs_unpacking(self, val_node: KwArgUnpackType) -> ValNodeUpdate:
        upg_kwargs_name = f"upg_kwargs_{self._tmp_var_index}"
        self._tmp_var_index += 1

        prefix_nodes: typ.List[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=upg_kwargs_name, ctx=ast.Store())],
                value=ast.Dict(keys=[], values=[], ctx=ast.Load()),
            )
        ]

        def add_items(val_node_items: typ.Iterable[typ.Tuple]):
            for key, val in val_node_items:
                if key is None:
                    prefix_nodes.append(ast.Expr(value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=upg_kwargs_name, ctx=ast.Load()),
                            attr="update",
                            ctx=ast.Load(),
                        ),
                        args=[val],
                        keywords=[],
                    )))
                else:
                    if isinstance(key, ast.Str):
                        key_val = key
                    elif isinstance(key, str):
                        key_val = ast.Str(s=key)
                    else:
                        raise TypeError(f"Invalid dict key {key}")

                    prefix_nodes.append(ast.Assign(targets=[
                        ast.Subscript(
                            slice=ast.Index(value=key_val),
                            value=ast.Name(id=upg_kwargs_name, ctx=ast.Load()),
                            ctx=ast.Store(),
                        ),
                    ], value=val))

        if isinstance(val_node, ast.Call):
            add_items((kw.arg, kw.value) for kw in val_node.keywords)
            args = val_node.args
            replacenemt_func = val_node.func
        elif isinstance(val_node, ast.Dict):
            args = []
            add_items(zip(val_node.keys, val_node.values))
            replacenemt_func = ast.Name(id="dict", ctx=ast.Load())
        else:
            raise TypeError(f"Unexpected val_node: {val_node}")

        new_val_node = ast.Call(
            func=replacenemt_func,
            args=args,
            keywords=[ast.keyword(
                arg=None, value=ast.Name(id=upg_kwargs_name, ctx=ast.Load())
            )],
        )
        del_node = ast.Delete(targets=[ast.Name(id=upg_kwargs_name, ctx=ast.Del())])
        return prefix_nodes, new_val_node, [del_node]

    def make_val_node_update(self, val_node: ast.expr) -> typ.Optional[ValNodeUpdate]:
        all_prefix_nodes: typ.List[ast.stmt] = []
        all_del_nodes: typ.List[ast.Delete] = []

        if isinstance(val_node, ArgUnpackNodes) and self.has_args_unpacking(val_node):
            prefix_nodes, new_val_node, del_nodes = self.expand_args_unpacking(val_node)
            assert not self.has_args_unpacking(new_val_node)
            all_prefix_nodes.extend(prefix_nodes)
            val_node = new_val_node
            all_del_nodes.extend(del_nodes)

        if isinstance(val_node, KwArgUnpackNodes) and self.has_kwargs_unpacking(val_node):
            prefix_nodes, new_val_node, del_nodes = self.expand_kwargs_unpacking(val_node)
            assert not self.has_kwargs_unpacking(new_val_node)
            all_prefix_nodes.extend(prefix_nodes)
            val_node = new_val_node
            all_del_nodes.extend(del_nodes)

        if len(all_prefix_nodes) > 0:
            assert len(all_del_nodes) > 0
            # TODO (mb 2018-06-22): We could simplify prefix nodes at
            #   this point, for example we could collapse consectuive
            #   calls to .extend which use literals into one, and
            #   replace the initial assignment with the first literal
            #   used in an .extend.
            return all_prefix_nodes, val_node, all_del_nodes
        else:
            return None

    def make_single_field_update(
        self, field_node: ast.expr
    ) -> typ.Optional[ValNodeUpdate]:

        if isinstance(field_node, ArgUnpackNodes + KwArgUnpackNodes):
            val_node_update = self.make_val_node_update(field_node)
            if val_node_update is not None:
                return val_node_update

        all_prefix_nodes: typ.List[ast.stmt] = []
        all_del_nodes: typ.List[ast.Delete] = []

        sub_fields = sorted(ast.iter_fields(field_node), key=node_field_sort_key)
        for sub_field_name, sub_field in sub_fields:
            # NOTE (mb 2018-06-23): field nodes should not have any body
            assert not is_block_field(sub_field_name, sub_field), f"""
            Unexpected block field {sub_field_name} for {field_node}
            """.strip()

            if not isinstance(sub_field, (list, ast.AST)):
                continue

            maybe_body_update = self.make_field_update(field_node, sub_field_name, sub_field)

            if maybe_body_update is None:
                continue

            prefix_nodes, del_nodes = maybe_body_update

            if isinstance(field_node, ast.Lambda):
                # NOTE (mb 2018-06-24): An update inside a lambda can reference
                #   parameters of the lambda. This means the prefix_nodes
                #   would carry over those references. So we convert the
                #   lambda to a temporary FunctionDef and replace it with
                #   a reference to that function def.
                temp_func_def = make_temp_lambda_as_def(field_node, prefix_nodes)
                all_prefix_nodes.append(temp_func_def)
                field_node = ast.Name(id=temp_func_def.name, ctx=ast.Load())
                all_del_nodes.append(ast.Delete(targets=[
                    ast.Name(id=temp_func_def.name, ctx=ast.Del())
                ]))
            else:
                all_prefix_nodes.extend(prefix_nodes)
                all_del_nodes.extend(del_nodes)

        if len(all_prefix_nodes) > 0:
            assert len(all_del_nodes) > 0
            return all_prefix_nodes, field_node, all_del_nodes
        else:
            return None

    def make_list_field_update(
        self, field_nodes: typ.List[ast.expr]
    ) -> typ.Optional[ListFieldNodeUpdate]:
        if len(field_nodes) == 0:
            return None

        all_prefix_nodes: typ.List[ast.stmt] = []
        new_field_nodes: typ.List[ast.expr] = []
        all_del_nodes: typ.List[ast.Delete] = []

        for field_node in field_nodes:
            body_update = self.make_single_field_update(field_node)
            if body_update is None:
                new_field_nodes.append(field_node)
            else:
                prefix_nodes, new_field, del_nodes = body_update
                all_prefix_nodes.extend(prefix_nodes)
                new_field_nodes.append(new_field)
                all_del_nodes.extend(del_nodes)

        if len(all_prefix_nodes) > 0:
            assert len(all_del_nodes) > 0
            assert len(new_field_nodes) > 0
            assert len(new_field_nodes) == len(field_nodes)
            return all_prefix_nodes, new_field_nodes, all_del_nodes
        else:
            return None

    def make_field_update(
        self, parent_node, field_name, field
    ) -> typ.Optional[ExpandedUpdate]:
        maybe_body_update: typ.Union[ListFieldNodeUpdate, ValNodeUpdate, None]

        if isinstance(field, list):
            maybe_body_update = self.make_list_field_update(field)
        else:
            maybe_body_update = self.make_single_field_update(field)

        if maybe_body_update is None:
            return None

        if isinstance(field, list):
            prefix_nodes, new_list_field, del_nodes = maybe_body_update
            setattr(parent_node, field_name, new_list_field)
        else:
            prefix_nodes, new_field, del_nodes = maybe_body_update
            setattr(parent_node, field_name, new_field)

        return prefix_nodes, del_nodes

    def apply_body_updates(self, body: typ.List[ast.stmt]):
        initial_len_body = len(body)
        prev_len_body = -1
        while prev_len_body != len(body):
            if len(body) > initial_len_body * 100:
                # NOTE (mb 2018-06-23): This should never happen,
                #   so it's an internal error, but rather than
                #   running out of memory, an early exception is
                #   raised.
                raise Exception("Expansion overflow")

            prev_len_body = len(body)

            o = 0
            # NOTE (mb 2018-06-17): Copy the body, because we
            #   modify it during iteration.
            body_copy = list(body)
            for i, node in enumerate(body_copy):
                fields = sorted(ast.iter_fields(node), key=node_field_sort_key)
                for field_name, field in fields:
                    if not isinstance(field, (list, ast.AST)):
                        continue

                    if is_block_field(field_name, field):
                        node_body = typ.cast(typ.List[ast.stmt], field)
                        self.apply_body_updates(node_body)
                        continue

                    maybe_body_update = self.make_field_update(node, field_name, field)

                    if maybe_body_update is None:
                        continue

                    prefix_nodes, del_nodes = maybe_body_update

                    body[i + o:i + o] = prefix_nodes
                    o += len(prefix_nodes)
                    if isinstance(body[i + o], ast.Return):
                        continue

                    # NOTE (mb 2018-06-24): We don't need to del if
                    #   we're at the end of a function block anyway.
                    o += 1
                    body[i + o:i + o] = del_nodes

    def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
        self.apply_body_updates(tree.body)
        return tree


# class GeneratorReturnToStopIterationExceptionFixer(FixerBase):
#
#     version_info = VersionInfo(
#         apply_since="2.0",
#         apply_until="3.3",
#     )
#
#     def __call__(self, cfg: common.BuildConfig, tree: ast.Module) -> ast.Module:
#         return tree
#
#     def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
#         # NOTE (mb 2018-06-15): What about a generator nested in a function definition?
#         is_generator = any(
#             isinstance(sub_node, (ast.Yield, ast.YieldFrom))
#             for sub_node in ast.walk(node)
#         )
#         if not is_generator:
#             return node
#
#         for sub_node in ast.walk(node):
#             pass


# YIELD_FROM_EQUIVALENT = """
# _i = iter(EXPR)
# try:
#     _y = next(_i)
# except StopIteration as _e:
#     _r = _e.value
# else:
#     while 1:
#         try:
#             _s = yield _y
#         except GeneratorExit as _e:
#             try:
#                 _m = _i.close
#             except AttributeError:
#                 pass
#             else:
#                 _m()
#             raise _e
#         except BaseException as _e:
#             _x = sys.exc_info()
#             try:
#                 _m = _i.throw
#             except AttributeError:
#                 raise _e
#             else:
#                 try:
#                     _y = _m(*_x)
#                 except StopIteration as _e:
#                     _r = _e.value
#                     break
#         else:
#             try:
#                 if _s is None:
#                     _y = next(_i)
#                 else:
#                     _y = _i.send(_s)
#             except StopIteration as _e:
#                 _r = _e.value
#                 break
# RESULT = _r
# """in_len_body


# class YieldFromFixer(FixerBase):
# # see https://www.python.org/dev/peps/pep-0380/
# NOTE (mb 2018-06-14): We should definetly do the most simple case
#   but maybe we can also detect the more complex cases involving
#   send and return values and at least throw an error

# class MetaclassFixer(TransformerFixerBase):
#
#     version_info = VersionInfo(
#         apply_since="2.0",
#         apply_until="2.7",
#     )
#
#     def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
#         #  class Foo(metaclass=X): => class Foo(object):\n  __metaclass__ = X


# class MatMulFixer(TransformerFixerBase):
#
#     version_info = VersionInfo(
#         apply_since="2.0",
#         apply_until="3.5",
#     )
#
#     def visit_Binop(self, node: ast.BinOp) -> ast.Call:
#         # replace a @ b with a.__matmul__(b)


# NOTE (mb 2018-06-24): I'm not gonna do it, but feel free to
#   implement it if you feel like it.
#
# class DecoratorFixer(FixerBase):
#     """Replaces use of @decorators with function calls
#
#     > @mydec1()
#     > @mydec2
#     > def myfn():
#     >     pass
#     < def myfn():
#     <     pass
#     < myfn = mydec2(myfn)
#     < myfn = mydec1()(myfn)
#     """
#
#     version_info = VersionInfo(
#         apply_since="2.0",
#         apply_until="2.4",
#     )
#

# NOTE (mb 2018-06-24): I'm not gonna do it, but feel free to
#   implement it if you feel like it.
#
# class WithStatementToTryExceptFixer(FixerBase):
#     """
#     > with expression as name:
#     >     name
#
#     < import sys
#     < __had_exception = False
#     < __manager = expression
#     < try:
#     <     name = manager.__enter__()
#     < except:
#     <     __had_exception = True
#     <     ex_type, ex_value, traceback = sys.exc_info()
#     <     __manager.__exit__(ex_type, ex_value, traceback)
#     < finally:
#     <     if not __had_exception:
#     <         __manager.__exit__(None, None, None)
#     """
#
#     version_info = VersionInfo(
#         apply_since="2.0",
#         apply_until="2.4",
#     )
#
