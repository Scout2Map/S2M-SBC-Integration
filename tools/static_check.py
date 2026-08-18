#!/usr/bin/env python3
"""Dependency-light static checks for the SBC integration repository."""

import ast
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (ROOT / 'scripts', ROOT / 'src')
FORBIDDEN_RUNTIME_TEXT = (
    'base_footprint',
    'micro_ros_agent',
    'nav2_minimal_tb3_sim',
    'scout_sim_bringup',
)
REMOVED_INSTALL_OPTIONS = ('--with-rplidar', '--with-vision')


def repository_files(pattern):
    return sorted(
        path for path in ROOT.rglob(pattern)
        if '.git' not in path.parts and '__pycache__' not in path.parts
    )


def main():
    errors = []

    for path in repository_files('*.py'):
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f'{path.relative_to(ROOT)}: Python parse: {exc}')

    for path in repository_files('package.xml') + repository_files('*.sdf'):
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            errors.append(f'{path.relative_to(ROOT)}: XML parse: {exc}')

    for path in repository_files('*-package.xml'):
        errors.append(
            f'{path.relative_to(ROOT)}: duplicate package manifest filename')

    for suffix in ('*.yaml', '*.yml', '*.repos'):
        for path in repository_files(suffix):
            try:
                list(yaml.safe_load_all(path.read_text(encoding='utf-8')))
            except (UnicodeError, yaml.YAMLError) as exc:
                errors.append(f'{path.relative_to(ROOT)}: YAML parse: {exc}')

    for source_root in SOURCE_ROOTS:
        for path in source_root.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            for forbidden in FORBIDDEN_RUNTIME_TEXT:
                if forbidden in text:
                    errors.append(
                        f'{path.relative_to(ROOT)}: obsolete runtime reference: {forbidden}'
                    )

    for path in repository_files('*.md'):
        text = path.read_text(encoding='utf-8')
        for option in REMOVED_INSTALL_OPTIONS:
            if option in text:
                errors.append(
                    f'{path.relative_to(ROOT)}: removed install option: {option}')
        for target in re.findall(r'\[[^]]+\]\(([^)]+)\)', text):
            if target.startswith(('http://', 'https://', '#')):
                continue
            local_target = target.split('#', 1)[0]
            if local_target and not (path.parent / local_target).resolve().exists():
                errors.append(
                    f'{path.relative_to(ROOT)}: broken local link: {target}'
                )

    dependencies = (ROOT / 'dependencies.repos').read_text(encoding='utf-8')
    urls = re.findall(r'^\s+url:\s+(\S+)\s*$', dependencies, re.MULTILINE)
    pins = re.findall(r'^\s+version:\s+([0-9a-f]+)\s*$', dependencies, re.MULTILINE)
    if not pins or len(pins) != len(urls):
        errors.append('dependencies.repos: every repository needs a commit pin')
    if any(len(pin) != 40 for pin in pins):
        errors.append('dependencies.repos: pins must be full 40-character commits')

    if errors:
        print('\n'.join(f'[FAIL] {error}' for error in errors))
        return 1

    print('[PASS] Python, XML, YAML, links, dependency pins and runtime references')
    return 0


if __name__ == '__main__':
    sys.exit(main())
